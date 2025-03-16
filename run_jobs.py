from app.scheduled_jobs import run_all_jobs

if __name__ == "__main__":
    print("Kör schemalagda jobb manuellt...")
    run_all_jobs()
    print("Schemalagda jobb slutförda")