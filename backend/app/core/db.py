import os
import logging
from sqlmodel import create_engine, SQLModel, Session
from app.core.config import settings

logger = logging.getLogger(__name__)

db_url = settings.resolved_database_url
is_sqlite = "sqlite" in db_url
is_serverless = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

# connect_args with timeout to prevent SQLite database lock errors
engine = create_engine(
    db_url,
    echo=False,
    connect_args={"check_same_thread": False, "timeout": 30} if is_sqlite else {}
)

def init_db():
    try:
        from app.models.entities import (
            Job, Requirement, Repository, Assessment, Citation,
            AuditHistory, WebhookEvent, LearningResourceCache
        )
        # Configure SQLite pragma settings safely
        if is_sqlite:
            try:
                with engine.connect() as conn:
                    if not is_serverless:
                        conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
                    else:
                        conn.exec_driver_sql("PRAGMA journal_mode=MEMORY;")
                    conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
            except Exception as e:
                logger.warning("Could not set SQLite PRAGMA: %s", e)

        # Create all tables if they don't exist
        SQLModel.metadata.create_all(engine)

        # Run non-destructive column migrations
        if is_sqlite:
            try:
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
            except Exception as e:
                logger.warning("SQLite migration warning: %s", e)
    except Exception as e:
        logger.error("Database init_db exception: %s", e)

def get_session():
    with Session(engine) as session:
        yield session
