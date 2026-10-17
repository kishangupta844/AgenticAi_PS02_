from sqlmodel import create_engine, SQLModel, Session
from app.core.config import settings

# connect_args with timeout to prevent SQLite database lock errors
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30} if "sqlite" in settings.DATABASE_URL else {}
)

def init_db():
    from app.models.entities import Job, Requirement, Repository, Assessment, Citation, AuditHistory, WebhookEvent, LearningResourceCache
    # Enable WAL mode for high concurrency in SQLite
    if "sqlite" in settings.DATABASE_URL:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
    SQLModel.metadata.create_all(engine)
    # create_all does not add columns to tables that already exist
    if "sqlite" in settings.DATABASE_URL:
        with engine.connect() as conn:
            # Migration for assessment
            cols_assessment = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(assessment)").fetchall()]
            if cols_assessment:
                if "llm_model" not in cols_assessment:
                    conn.exec_driver_sql("ALTER TABLE assessment ADD COLUMN llm_model VARCHAR")
                if "llm_raw_response" not in cols_assessment:
                    conn.exec_driver_sql("ALTER TABLE assessment ADD COLUMN llm_raw_response TEXT")

            # Migration for job
            cols_job = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(job)").fetchall()]
            if cols_job and "role_profile" not in cols_job:
                conn.exec_driver_sql("ALTER TABLE job ADD COLUMN role_profile TEXT")

            # Migration for requirement
            cols_req = [r[1] for r in conn.exec_driver_sql("PRAGMA table_info(requirement)").fetchall()]
            if cols_req and "aliases" not in cols_req:
                conn.exec_driver_sql("ALTER TABLE requirement ADD COLUMN aliases TEXT")

            conn.commit()

def get_session():
    with Session(engine) as session:
        yield session
