# Inteligentne Układanie Planów Pracy z Wykorzystaniem LLM

> **Problem:** automatyczne generowanie planów lekcji dla nauczycieli pracujących w wielu szkołach jednocześnie, z wykorzystaniem opisu w języku naturalnym jako wejścia.

### 1.1 Nauczyciel w wielu szkołach

Nauczyciel pracujący jednocześnie w wielu szkołach wprowadza dodatkowe wymiary problemu:

- **Ograniczenia transportowe:** czas dojazdu między szkołami tworzy *okna niedostępności* zależne od par lokalizacji i środka transportu
- **Odrębne administracje:** każda szkoła ma własny plan, który musi być globalnie spójny (dodatkowo, nauczyciel może mieć już jeden z planów ułożony i niemożliwy do zmian, a drugi w trakcie układania)
- **Niesymetryczne zasoby:** ta sama sala istnieje tylko w jednej szkole; nauczyciel istnieje we wszystkich
- **Problemy kaskadowe:** zmiana planu w szkole A może naruszyć ograniczenia w szkole B

### 1.2 Dlaczego nie wystarczy klasyczny solwer?

| Etap | Podejście naiwne | Rzeczywistość |
|------|-----------------|---------------|
| Zbieranie wymagań | Opis słowny od dyrektora/planisty | Nieprecyzyjny, niekompletny, sprzeczny |
| Formalizacja | Ręczne tłumaczenie na model | Czasochłonne, wymaga eksperta |
| Zmiana wymagań | Modyfikacja kodu modelu | Niepraktyczne/niemożliwe dla użytkownika końcowego |
| Wyjaśnienie błędu | "Solver nie znalazł rozwiązania" | Niezrozumiałe dla nauczyciela |

System reprezentacji pośredniej i doprecyzowującego dialogu z LLM powinien rozwiązać te problemy.
---

## 2. Architektura systemu - przegląd

```
┌─────────────────────────────────────────────────────────────────┐
│                        UŻYTKOWNIK                               │
│              (dyrektor, planista, nauczyciel)                   │
└────────────────────────┬────────────────────────────────────────┘
                         │ opis w języku naturalnym
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WARSTWA A: NL → JSON                            │
│  LLM tłumaczy opis na ustrukturyzowany schemat JSON             │
│  • wyodrębnia ograniczenia twarde i miękkie                     │
│  • identyfikuje luki i niespójności                             │
│  • oddziela dane wejściowe od domyślnych założeń                │
└────────────────────────┬───────────────────────────────────────-┘
                         │ schemat z listą luk (clarification_needed)
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WARSTWA B: MODUŁ DIALOGOWY                      │
│  • priorytetyzuje pytania (tylko krytyczne)                     │
│  • prezentuje luki użytkownikowi w zrozumiałej formie           │
│  • aktualizuje schemat JSON na podstawie odpowiedzi             │
│  • wykrywa sprzeczności między odpowiedziami                    │
└────────────────────────┬────────────────────────────────────────┘
                         │ kompletny, zwalidowany schemat
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WARSTWA C: JSON → OR-TOOLS                      │
│  Deterministyczny translator (bez LLM)                          │
│  • generuje zmienne decyzyjne                                   │
│  • dodaje ograniczenia twarde                                   │
│  • definiuje funkcję celu z wagami ograniczeń miękkich          │
└────────────────────────┬────────────────────────────────────────┘
                         │ model CP-SAT
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                 WARSTWA D: SOLVER + WYJAŚNIENIA                 │
│  OR-Tools CP-SAT                                                │
│  • w przypadku sukcesu: plan lekcji                             │
│  • w przypadku infeasibility: LLM wyjaśnia konflikt             │
└─────────────────────────────────────────────────────────────────┘
```

**Założenie:** LLM operuje wyłącznie w warstwach A i B (język naturalny ↔ ustrukturyzowane dane). Warstwy C i D są deterministyczne, nie ma miejsca na halucynacje w kodzie generującym model dla solvera.

---

## 3. Warstwa A: Tłumaczenie języka naturalnego na ustrukturyzowany schemat

Warstwa A odpowiada za pierwsze tłumaczenie: z opisu słownego do ustrukturyzowanego schematu. LLM nie generuje kodu, tylko wypełnia zdefiniowany przez system schemat JSON.

**Wyodrębnianie ograniczeń:** klasyfikacja każdego jako:
- ograniczenie **twarde** - naruszenie jest niedopuszczalne
- ograniczenie **miękkie** - naruszenie jest dopuszczalne, ale karane

Inne zadania:
- Identyfikacja zasobów, czyli rozpoznanie podmiotów w opisie: nauczyciele, klasy, sale, przedmioty, timesloty.
- Ekstrakcja parametrów: liczby, nazwy, zakresy wartości (np. "5 dni roboczych", "co najwyżej 6 lekcji dziennie").
- Identyfikacja miejsc, gdzie opis jest niekompletny lub niejednoznaczny (luki logiczne).
- Jawne wskazanie, co LLM "dopowiedział" na podstawie wiedzy dziedzinowej, a co wprost wynikało z opisu (pytanie, jak sprawdzić poprawność tego wskazania, czy to oczywiste).

### 3.1 Inżynieria promptów dla warstwy A

Kluczowe elementy:
- Dostarczenie LLM słownika pojęć dziedzinowych z definicjami (co to jest "slot", "ograniczenie twarde", "ograniczenie miękkie" w kontekście planowania lekcji).
- Przykłady few-shot - Kilka par (opis → schemat) z adnotacjami, dlaczego dane zdanie zostało zakwalifikowane jako ograniczenie twarde vs miękkie. 
- Dokładna specyfikacja schematu JSON z typami i opisami pól. LLM powinien wiedzieć, że pola `assumptions_made` i `clarification_needed` są obowiązkowe i że puste listy są niedopuszczalne.
- Instrukcja konserwatywności: "Jeśli nie masz pewności, czy coś jest ograniczeniem twardym czy miękkim, zaklasyfikuj jako miękkie i dodaj do `clarification_needed`."
- Instrukcja jawności założeń: "Każde założenie, które dodajesz samodzielnie, musi znaleźć się w `assumptions_made` (audyt)."
  
### 3.2 Potencjalne problemy i pomysły na rozwiązania

| Problem | Opis | Rozwiązanie |
|---------|------|-----------|
| Klasyfikacja twarde/miękkie | LLM nie jest pewny, czy "najlepiej żeby" to nakaz czy preferencja | Analiza słów wskazujących na priorytet (raczej, najlepiej, jeśli możliwe); domyślnie miękkie |
| Pominięcie kontekstu | LLM ignoruje część opisu przy długich wejściach | Chunking wejścia + weryfikacja kompletności |
| Halucynowane ograniczenia | LLM dodaje ograniczenia niewymienione w opisie | Wymaganie cytatu źródłowego dla każdego ograniczenia |
| Nierozpoznany podmiot | Mogą to być np. zaimki, które odnoszą się do nauczyciela wymienionego wcześniej | Coreference resolution (znaleźć więcej informacji) w prompcie, może preprocessing? Pytanie, czy będzie to problem każdego modelu, czy jest to już nieaktualne |
| Sprzeczność w opisie | "Pani X jest dostępna rano" + "Pani X zaczyna o 14:00" | Flagowanie sprzeczności przed tłumaczeniem |

---

## 4. Warstwa B: Moduł dialogowy z doprecyzowaniem wymagań

Warstwa B przekształca zidentyfikowane luki w dialog z użytkownikiem, ale robi to **inteligentnie**: nie zasypuje pytaniami, pyta tylko o to, co rzeczywiście blokuje solvera lub istotnie wpływa na jakość planu.
Nie wszystkie luki są równie ważne. System powinien klasyfikować pytania według priorytetu:

**Krytyczne (blokujące):** Bez odpowiedzi solver nie może uruchomić się poprawnie.
- Ile slotów ma dzień?
- Ile lekcji tygodniowo z danego przedmiotu ma każda klasa?
- Jakie sale są dostępne?

**Ważne (wpływające na jakość):** Bez odpowiedzi solver użyje domyślnych wartości, ale jakość planu może być niska.
- Jakie wagi przypisać preferencjom (np. "raczej rano")?
- Czy nauczyciel preferuje przerwy między lekcjami?

**Opcjonalne (doprecyzowujące):** System może działać sensownie bez odpowiedzi.
- Czy jest preferowany dzień, w którym dana klasa ma więcej lekcji?
- Czy nauczyciel chce mieć ten sam plan co tydzień?

Strategia: w pierwszej iteracji zadać tylko pytania krytyczne. Po odpowiedzi zadać pytania ważne. Opcjonalne tylko na żądanie (możliwe że tutaj wymagałoby doprecyzowania, w jakich konkretnie sytuacjach).

### 4.1 Format dialogu

Pytania powinny być prezentowane w sposób zrozumiały dla osoby niebędącej ekspertem od optymalizacji. Zamiast:

> "Czy ograniczenie dotyczące nauczyciela T_Kowalski ma typ `hard` czy `soft`?"

System powinien pytać:

> "Pan Kowalski jest niedostępny w poniedziałek i środę po 13:00. Czy to oznacza, że w żadnym wypadku nie może mieć wtedy lekcji (bezwzględny zakaz), czy raczej że lepiej żeby nie miał, ale w wyjątkowej sytuacji jest to możliwe?"

Opcje odpowiedzi mogą być ustrukturyzowane (przyciski, lista wyboru) lub tekstowe, co zależy od interfejsu. Generalnie jeśli odpowiedź zawierałaby np. przyciski, to pozbywamy się kilku problemów np. błędów ludzkich, tłumaczenia tego znowu na zmienne. Niektóre chaty LLM już stosują takie pytania doprecyzowujące z listami wyboru i zdaje się to działać dobrze.

### 4.2 Aktualizacja schematu

Każda odpowiedź użytkownika jest przetwarzana przez LLM, który:
- aktualizuje odpowiednie pole w schemacie
- przesuwa ograniczenie z `clarification_needed` do odpowiedniej listy ograniczeń
- sprawdza, czy odpowiedź nie tworzy nowych sprzeczności z już zdefiniowanymi ograniczeniami
- generuje ewentualne nowe pytania wynikające z odpowiedzi

System powinien wykryć sprzeczności **przed uruchomieniem solvera** i poinformować użytkownika z wyjaśnieniem. Po każdej aktualizacji schematu potrzebna jest walidacja logiczna, czyli sprawdzenie niezmiennych warunków (np. łączna liczba wymaganych lekcji ≤ dostępne sloty × liczba nauczycieli).

### 4.3 Potwierdzenie interpretacji przed solverem

Przed uruchomieniem solvera system prezentuje podsumowanie interpretacji w języku naturalnym:

> "Rozumiem, że:
> - Tydzień składa się z 5 dni, każdy dzień ma 8 slotów lekcyjnych
> - Pan Kowalski **nie może** mieć lekcji w poniedziałek i środę po slocie 4
> - Klasa 3A powinna mieć matematykę **najlepiej** w slotach 1-4 (preferowane, ale nie wymagane)
> - Wszystkie klasy mają po 4 lekcje matematyki tygodniowo
>
> Czy to jest poprawne? Czy coś pominąłem lub źle zrozumiałem?"

Ten krok może być kluczowy dla redukcji błędów wynikających z błędnej interpretacji. Może nawet dla zaufania użytkownika?

---

## 5. Warstwa C: Deterministyczny translator schemat → OR-Tools

Po tym, jak schemat jest kompletny i zwalidowany, **żaden LLM nie dotyka kodu generującego model dla solvera**. Translator jest zwykłym, deterministycznym programem, który można przetestować.

Zalety:
- Błędy w translatorze są wykrywalne i naprawialne
- Translator można pokryć testami jednostkowymi
- Ten sam schemat zawsze daje ten sam model CP-SAT
- Nie ma ryzyka, że LLM "dopowie" dodatkowe ograniczenie w kodzie

### 5.1 Architektura translatora

Translator działa jako stos transformacji:

```
JSON
  ↓
[Parser i Validator] - sprawdza kompletność i typy pól
  ↓
[Resource Builder] - tworzy słowniki zasobów (nauczyciele, klasy, sale, sloty)
  ↓
[Variable Generator] - tworzy zmienne decyzyjne CP-SAT
  ↓
[Hard Constraint Encoder] - dodaje ograniczenia twarde
  ↓
[Soft Constraint Encoder] - dodaje zmienne karne i funkcję celu
  ↓
Model CP-SAT
```

todo: dopracowanie konkretnego schematu działania.

## 6. Warstwa D: Solver i obsługa infeasibility ****

Gdy solver zwróci `INFEASIBLE`, użytkownik dostaje informację bezużyteczną ("nie znalazłem planu"). Możliwy schemat działania:

**Krok 1: Identyfikacja konfliktów**
OR-Tools może generować *Infeasibility Explanations* (IIS - Irreducible Infeasible Subsystem). To minimalne podzbiory ograniczeń, które razem są sprzeczne.

**Krok 2: Tłumaczenie z powrotem na język naturalny**
LLM tłumaczy techniczny opis konfliktu na zrozumiałe zdanie:

> "Nie udało się ułożyć planu, ponieważ Pan Kowalski jest przypisany do 6 lekcji w środę, ale jest dostępny tylko w slotach 1-3, a jedna lekcja trwa 1 slot. Możliwe rozwiązania: (a) zmniejsz liczbę lekcji Pana Kowalskiego w środę, (b) wydłuż jego dostępność, (c) przypisz część lekcji innemu nauczycielowi."

**Krok 3: Sugestie relaksacji**
System może zaproponować, które ograniczenia miękkie warto osłabić lub usunąć, żeby plan stał się możliwy do ułożenia.

---

## 7. Projektowanie schematu danych (DSL - Domain Specific Language)

DSL musi być dostatecznie ekspresywny, żeby pokryć wszystkie realistyczne wymagania use case'u, ale nie tak ogólny, żeby stał się nowym językiem programowania. Sugerowany zakres dla use case nauczycielskiego:

**Zasoby (entities):**
- Nauczyciele (z atrybutami: imię, szkoły, dostępność)
- Klasy uczniowskie (z atrybutami: szkoła, poziom)
- Sale (z atrybutami: szkoła, pojemność, typ np. sala informatyczna)
- Przedmioty
- Timesloty (dni × godziny)

**Ograniczenia twarde (standardowe):**
- `no_double_booking` - nauczyciel/sala/klasa nie może być w dwóch miejscach jednocześnie
- `teacher_unavailable` - blokada konkretnych slotów
- `teacher_travel_time` - minimalny odstęp między lekcjami w różnych szkołach
- `subject_frequency` - ile razy w tygodniu dana klasa ma dany przedmiot
- `room_required_type` - niektóre zajęcia wymagają specjalnej sali

**Ograniczenia miękkie (standardowe):**
- `prefer_morning` / `prefer_afternoon`
- `prefer_compact_schedule` - minimalizacja okienek
- `prefer_consistent_slots` - ten sam przedmiot o tej samej porze każdego tygodnia
- `prefer_room` - preferencja konkretnej sali
- `avoid_last_slot` - unikanie ostatniej lekcji w dniu

DSL powinien mieć numer wersji (`"dsl_version": "1.2"`). Translator wspiera konkretne wersje. Umożliwia to ewolucję schematu bez łamania kompatybilności z zapisanymi instancjami problemów.

### 7.1 DSL jako format wymiany

Schemat DSL może pełnić podwójną rolę:
- **Format wejściowy:** z opisu naturalnego przez LLM
- **Format eksportu:** zapisany plik `.json` z opisem problemu, który można edytować ręcznie, wersjonować w git, przesyłać między systemami

Może pozwoliłoby to na budowę biblioteki znanych problemów (benchmarki, przykłady).
---

## 8. Ukryte założenia - taksonomia i strategie wykrywania

Jest tutaj przynajmniej kilka kategorii:

**Założenia dotyczące struktury problemu**:
- Liczba slotów w dniu
- Długość tygodnia roboczego
- Czy plan jest tygodniowy, czy może dwutygodniowy (A/B)
- Czy przerwy są slotami (i mogą być zajęte) czy przerwami (i nie mogą)

**Założenia dotyczące zasobów:**
- Czy każdy przedmiot ma dokładnie jednego nauczyciela, czy może więcej?
- Czy klasy uczniowskie są homogeniczne (wszyscy mają ten sam plan)?
- Czy sale mają pojemność, która ogranicza przypisanie klas?

**Założenia dotyczące ograniczeń:**
- Domyślna twardość ograniczeń (co jest twarde, co miękkie, gdy użytkownik nie mówi wprost)
- Domyślna liczba lekcji tygodniowo, gdy nie podano
- Czy "dostępny od 9:00" oznacza że może zaczynać o 9:00 czy że musi być na miejscu o 9:00?

**Założenia dotyczące funkcji celu:**
- Czy wszystkie preferencje są równoważne, czy niektóre są ważniejsze?
- Co jest priorytetem: minimalizacja okienek vs zgodność z preferencjami?

### 8.1 Wykrywanie

**Lista obowiązkowych pól schematu**
Każde pole w DSL oznaczone jako `required: true` musi być wypełnione przez LLM lub pozyskane przez dialog. Jeśli LLM wypełnia je bez podstawy w opisie, to musi to odnotować w `assumptions_made`.

**Analiza słów sygnalizujących rodzaj ograniczenia**
Słowa takie jak "raczej", "najlepiej", "jeśli możliwe", "zwykle", "zazwyczaj" sygnalizują ograniczenia miękkie lub niepewność. LLM powinien być instruowany, żeby te słowa wykrywał i odpowiednio klasyfikował.

**Detekcja sprzeczności**
Przed dialogiem sprawdzenie, czy opis zawiera wewnętrzne sprzeczności, np. "nauczyciel jest dostępny cały czas" + "nauczyciel nie jest dostępny w piątki".

---

## 9. Walidacja poprawności interpretacji

### 9.1 Wielopoziomowa walidacja

Walidacja powinna następować na kilku poziomach:

**Poziom 1: Walidacja schematu (syntaktyczna)**
JSON jest poprawny składniowo i zgodny ze schematem (typy pól, wymagane klucze). Narzędzie: `jsonschema`.

**Poziom 2: Walidacja logiczna (semantyczna)**
Sprawdzenie prostych niezmienników bez uruchamiania solvera:
- Czy każda klasa ma przypisane lekcje?
- Czy każde zajęcie ma przypisanego nauczyciela?
- Czy sumaryczna liczba lekcji nie przekracza dostępnych slotów?
- Czy nauczyciel jest dostępny wystarczająco długo dla przypisanych zajęć?

**Poziom 3: Walidacja przez partial solving**
Możliwe, że uruchomienie solvera na uproszczonej wersji problemu (tylko ograniczenia twarde, mała instancja) przyda się do szybkiej detekcji oczywistych konfliktów.

**Poziom 4: Walidacja przez użytkownika**
Podsumowanie interpretacji w języku naturalnym.

### 9.2 Metryki jakości interpretacji

todo

---

## 10. Ewaluacja systemu

Można stworzyć własny zbiór benchmarkowy:
- Opisy na różnych poziomach kompletności (od bardzo szczegółowych do bardzo ogólnych)
- Opisy z celowo wprowadzonymi sprzecznościami
- Opisy w różnych stylach (formalny, potoczny, punktowany, narracyjny)
- Opisy z typowymi pułapkami (zaimki, elipsy, domyślna wiedza dziedzinowa)

## 11. Ryzyka i ograniczenia

**LLM nie generuje poprawnego JSON**
LLM może produkować niepoprawny JSON szczególnie dla złożonych opisów. Mitigacja: walidacja schematu + retry z komunikatem błędu, structured outputs (jeśli model to wspiera np. Anthropic / OpenAI).

**Prompt injection**
Użytkownik może próbować "przejąć" zachowanie LLM przez sprytnie sformułowany opis. Mitigacja: separacja systemu od wejścia użytkownika, sanityzacja wejścia.

**Skalowalność solvera**
Dla bardzo dużych instancji (wiele szkół, nauczycieli) CP-SAT może nie znaleźć rozwiązania w rozsądnym czasie. Mitigacja: dekompozycja problemu, time limit z best-so-far, może metaheurystyki jako fallback.

**Halucynacje LLM w identyfikacji ograniczeń**
LLM może "wymyślić" ograniczenia nieobecne w opisie. Mitigacja: cytaty źródłowe, potwierdzenie przez użytkownika.

---

## 12. Możliwe kierunki rozszerzenia

### 12.1 Wyjaśnialność planu

Nie tylko wygenerowanie planu, ale uzasadnienie każdej decyzji: "Matematyka 3A jest w środę o 9:00, ponieważ jest to jedyny slot spełniający dostępność Pana Kowalskiego i preferencję poranną klasy."

### 12.2 Wsparcie dla planów dwutygodniowych i rotacyjnych

Rozszerzenie dla szkół z rotującymi grupami. Rozszerzenie DSL o te koncepty.

### 12.3 Integracja z zewnętrznymi systemami

Import dostępności z kalendarza Google/Outlook? Czy da się integrować z systemami jak Librus?
---

### 13. Priorytety dla pracy

**Must have:**
- DSL schema (v1.0) z podstawowymi typami ograniczeń
- Działający pipeline NL → DSL → OR-Tools dla prostych przypadków
- Moduł dialogowy dla pytań krytycznych
- Ewaluacja na co najmniej 20 przykładach

**Should have:**
- Walidacja logiczna przed solverem
- Tłumaczenie infeasibility na język naturalny
- Porównanie z naiwnym podejściem (LLM → kod bezpośrednio)

**Nice to have:**
- Fine-tuning LLM
- Wsparcie dla wielu szkół jednocześnie
- Interfejs webowy

---
