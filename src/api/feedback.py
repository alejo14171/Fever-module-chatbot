"""
Feedback system for chat interactions.
Handles feedback submission and retrieval from PostgreSQL.
"""
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
import psycopg
from psycopg.rows import dict_row
from pydantic import BaseModel, Field


DB_URI = os.getenv("DB_URI")


class FeedbackSubmission(BaseModel):
    """Model for feedback submission"""
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    clarity: str = Field(..., pattern="^(Sí|Más o menos|No)$")
    helpfulness: str = Field(..., pattern="^(Sí|Parcialmente|No)$")
    medicalGuidance: str = Field(..., pattern="^(Sí|No|No era necesario decirlo en este caso)$")
    tone: str = Field(..., pattern="^(Sí|Un poco frío|Inadecuado)$")
    confusion: str = Field(..., pattern="^(Sí|No)$")
    recommendation: str = Field(..., pattern="^(Definitivamente sí|Probablemente sí|No estoy seguro|Probablemente no|Definitivamente no)$")
    improvements: Optional[str] = None
    sessionId: str = Field(..., min_length=1, max_length=255)


class FeedbackResponse(BaseModel):
    """Model for feedback response"""
    success: bool
    message: str
    feedback_id: Optional[int] = None


class FeedbackStatsResponse(BaseModel):
    """Model for feedback statistics response"""
    success: bool
    stats: Dict[str, Any]


class FeedbackListResponse(BaseModel):
    """Model for feedback list response"""
    success: bool
    total: int
    feedback: List[Dict[str, Any]]


def get_db_connection():
    """Get a database connection"""
    return psycopg.connect(DB_URI)


def create_feedback_table():
    """
    Create the feedback table if it doesn't exist.
    Should be called during application startup.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    id SERIAL PRIMARY KEY,
                    first_name VARCHAR(100) NOT NULL,
                    last_name VARCHAR(100) NOT NULL,
                    clarity VARCHAR(50) NOT NULL,
                    helpfulness VARCHAR(50) NOT NULL,
                    medical_guidance VARCHAR(100) NOT NULL,
                    tone VARCHAR(50) NOT NULL,
                    confusion VARCHAR(10) NOT NULL,
                    recommendation VARCHAR(50) NOT NULL,
                    improvements TEXT,
                    session_id VARCHAR(255) NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT check_clarity CHECK (clarity IN ('Sí', 'Más o menos', 'No')),
                    CONSTRAINT check_helpfulness CHECK (helpfulness IN ('Sí', 'Parcialmente', 'No')),
                    CONSTRAINT check_medical_guidance CHECK (medical_guidance IN ('Sí', 'No', 'No era necesario decirlo en este caso')),
                    CONSTRAINT check_tone CHECK (tone IN ('Sí', 'Un poco frío', 'Inadecuado')),
                    CONSTRAINT check_confusion CHECK (confusion IN ('Sí', 'No')),
                    CONSTRAINT check_recommendation CHECK (recommendation IN ('Definitivamente sí', 'Probablemente sí', 'No estoy seguro', 'Probablemente no', 'Definitivamente no'))
                );

                -- Create indexes
                CREATE INDEX IF NOT EXISTS idx_feedback_session_id ON feedback(session_id);
                CREATE INDEX IF NOT EXISTS idx_feedback_timestamp ON feedback(timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_feedback_name ON feedback(last_name, first_name);
            """)
            conn.commit()
            print("✅ Feedback table created successfully")
    except Exception as e:
        conn.rollback()
        print(f"❌ Error creating feedback table: {e}")
        raise
    finally:
        conn.close()


def insert_feedback(feedback: FeedbackSubmission) -> int:
    """
    Insert a new feedback record into the database.

    Args:
        feedback: FeedbackSubmission model with all feedback data

    Returns:
        The ID of the newly created feedback record

    Raises:
        Exception if insertion fails
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO feedback (
                    first_name, last_name, clarity, helpfulness,
                    medical_guidance, tone, confusion, recommendation,
                    improvements, session_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                feedback.firstName,
                feedback.lastName,
                feedback.clarity,
                feedback.helpfulness,
                feedback.medicalGuidance,
                feedback.tone,
                feedback.confusion,
                feedback.recommendation,
                feedback.improvements,
                feedback.sessionId
            ))
            feedback_id = cur.fetchone()[0]
            conn.commit()
            print(f"✅ Feedback #{feedback_id} saved for session {feedback.sessionId}")
            return feedback_id
    except Exception as e:
        conn.rollback()
        print(f"❌ Error inserting feedback: {e}")
        raise
    finally:
        conn.close()


def get_all_feedback() -> List[Dict[str, Any]]:
    """
    Retrieve all feedback records from the database.

    Returns:
        List of feedback records as dictionaries
    """
    conn = get_db_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("""
                SELECT
                    id,
                    first_name as "firstName",
                    last_name as "lastName",
                    clarity,
                    helpfulness,
                    medical_guidance as "medicalGuidance",
                    tone,
                    confusion,
                    recommendation,
                    improvements,
                    session_id as "sessionId",
                    timestamp
                FROM feedback
                ORDER BY timestamp DESC
            """)
            results = cur.fetchall()
            # Convert RealDictRow to regular dict and handle datetime
            feedback_list = []
            for row in results:
                row_dict = dict(row)
                if row_dict.get('timestamp'):
                    row_dict['timestamp'] = row_dict['timestamp'].isoformat()
                feedback_list.append(row_dict)
            return feedback_list
    except Exception as e:
        print(f"❌ Error retrieving feedback: {e}")
        raise
    finally:
        conn.close()


def get_feedback_stats() -> Dict[str, Any]:
    """
    Calculate aggregated statistics for all feedback fields.

    Returns:
        Dictionary with statistics for each feedback field
    """
    conn = get_db_connection()
    try:
        with conn.cursor(row_factory=dict_row) as cur:
            # Get total count
            cur.execute("SELECT COUNT(*) as total FROM feedback")
            total = cur.fetchone()['total']

            stats = {"total": total}

            # Get counts for each field
            fields = [
                'clarity',
                'helpfulness',
                'medical_guidance',
                'tone',
                'confusion',
                'recommendation'
            ]

            for field in fields:
                cur.execute(f"""
                    SELECT {field}, COUNT(*) as count
                    FROM feedback
                    GROUP BY {field}
                    ORDER BY count DESC
                """)
                results = cur.fetchall()
                # Convert to camelCase for response
                field_camel = ''.join(word.capitalize() if i > 0 else word
                                     for i, word in enumerate(field.split('_')))
                stats[field_camel] = {row[field]: row['count'] for row in results}

            return stats
    except Exception as e:
        print(f"❌ Error calculating feedback stats: {e}")
        raise
    finally:
        conn.close()
