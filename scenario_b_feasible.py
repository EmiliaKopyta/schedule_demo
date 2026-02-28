from ortools.sat.python import cp_model
from plot_schedule import plot_schedule

model = cp_model.CpModel()

# --- Data ---
students = ["S1", "S2", "S3"]
subjects = ["A", "B", "C", "D", "E"]
days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
periods = range(5)

rooms = {
    "A": "Room_A",
    "B": "Room_B",
    "C": "Room_C",
    "D": "Room_D",
    "E": "Room_E"
}

teachers = {
    "A": "T1",
    "B": "T2",
    "C": "T3",
    "D": "T4",
    "E": "T5"
}

subject_hours = {
    "A": 2,
    "B": 2,
    "C": 5,
    "D": 1,
    "E": 1
}

# --- Quick sanity check before solving ---
required_A_lessons = len(students) * subject_hours["A"]   # 3 * 2 = 6
allowed_days_t1 = [1, 2]  # Tuesday, Wednesday

t1_capacity = len(list(periods)) * len(allowed_days_t1)

print("Quick sanity check:")
print(f"Required A lessons: {required_A_lessons}")
print(f"T1 capacity on allowed days: {t1_capacity}")

# --- Decision Variables ---
x = {}
for s in students:
    for subj in subjects:
        for d in range(len(days)):
            for p in periods:
                for r in rooms.values():
                    x[(s, subj, d, p, r)] = model.NewBoolVar(
                        f"{s}_{subj}_{d}_{p}_{r}"
                    )

# --- 1. Each student gets correct weekly hours per subject ---
for s in students:
    for subj in subjects:
        model.Add(
            sum(
                x[(s, subj, d, p, r)]
                for d in range(len(days))
                for p in periods
                for r in rooms.values()
            ) == subject_hours[subj]
        )

# --- 2. A student cannot have two lessons at same time ---
for s in students:
    for d in range(len(days)):
        for p in periods:
            model.Add(
                sum(
                    x[(s, subj, d, p, r)]
                    for subj in subjects
                    for r in rooms.values()
                ) <= 1
            )

# --- 3. Room cannot host two classes at same time ---
for r in rooms.values():
    for d in range(len(days)):
        for p in periods:
            model.Add(
                sum(
                    x[(s, subj, d, p, r)]
                    for s in students
                    for subj in subjects
                ) <= 1
            )

# --- 4. Teacher cannot teach two classes at same time ---
for subj in subjects:
    for d in range(len(days)):
        for p in periods:
            model.Add(
                sum(
                    x[(s, subj, d, p, r)]
                    for s in students
                    for r in rooms.values()
                ) <= 1
            )

# --- 5. Teacher 1 only works Tuesday and Wednesday ---
for s in students:
    for subj in subjects:
        if teachers[subj] == "T1":
            for d in range(len(days)):
                if d not in allowed_days_t1:
                    for p in periods:
                        for r in rooms.values():
                            model.Add(x[(s, subj, d, p, r)] == 0)

# --- Soft Constraint: Prefer dedicated room ---
penalties = []
for s in students:
    for subj in subjects:
        preferred_room = rooms[subj]
        for d in range(len(days)):
            for p in periods:
                for r in rooms.values():
                    if r != preferred_room:
                        penalties.append(x[(s, subj, d, p, r)])

model.Minimize(sum(penalties))

# --- Solve ---
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 10
solver.parameters.log_search_progress = True

status = solver.Solve(model)

status_name = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}.get(status, str(status))

print("\nSolver status:", status_name)

if status in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    entries = []
    for s in students:
        print(f"\nSchedule for {s}")
        for d in range(len(days)):
            for p in periods:
                found = False
                for subj in subjects:
                    for r in rooms.values():
                        if solver.Value(x[(s, subj, d, p, r)]):
                            print(f"{days[d]} Period {p+1}: {subj} in {r}")
                            entries.append((s, d, p, subj, r))
                            found = True
                if not found:
                    print(f"{days[d]} Period {p+1}: ---")

    plot_schedule(
        entries=entries,
        students=students,
        days=days,
        periods=periods,
        output_path="scenario_b_gantt.png",
    )
else:
    print("No feasible schedule found.")
