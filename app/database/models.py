from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class Questionnaire(Base):
    __tablename__ = "questionnaires"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    code: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    


class CanonicalQuestion(Base):
    __tablename__ = "canonical_questions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    
    questionnaire_id: Mapped[int] = mapped_column(
    ForeignKey("questionnaires.id"),
    nullable=False,
    index=True,
    )
    

    code: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    test_psicolog: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    item_order: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    
    
    questionnaire = relationship(
        "Questionnaire"
    )
    
    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id",
            "test_psicolog",
            "item_order",
            name="uq_canonical_question",
        ),
    )


class QuestionVariant(Base):
    __tablename__ = "question_variants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    canonical_question_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_questions.id"),
        nullable=False,
        index=True,
    )

    questionnaire_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaires.id"),
        nullable=False,
        index=True,
    )
    
    # Actual answerable question:
    # Q12.1, Q12.2, Q13, etc.
    question_number: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    question: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    gender_form: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    file_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    parent_question_number: Mapped[str | None] = mapped_column(
        String(30),
        nullable=True,
    )

    parent_question: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    
    pair_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    pair_similarity: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )
    

    canonical_question = relationship(
        "CanonicalQuestion"
    )

    questionnaire = relationship(
        "Questionnaire"
    )

    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id",
            "file_name",
            "question_number",
            "gender_form",
            name="uq_question_variant",
        ),
    )

# ============================================================
# PARTICIPANTS
# ============================================================
class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )
    
    # Real participant identification from Excel
    subject_id: Mapped[int] = mapped_column(
        Integer,
        unique=True,
        nullable=False,
        index=True,
    )

   


class QuestionnaireSession(Base):
    __tablename__ = "questionnaire_sessions"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    participant_id: Mapped[int] = mapped_column(
        ForeignKey("participants.id"),
        nullable=False,
        index=True,
    )

    questionnaire_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaires.id"),
        nullable=False,
        index=True,
    )
    
    # Wording selected by the participant
    # 0 = male wording
    # 1 = female wording

    wording_form: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    
    
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    score: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    participant = relationship("Participant")
    questionnaire = relationship("Questionnaire")


class Response(Base):
    __tablename__ = "responses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    session_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaire_sessions.id"),
        nullable=False,
        index=True,
    )

    question_variant_id: Mapped[int] = mapped_column(
        ForeignKey("question_variants.id"),
        nullable=False,
        index=True,
    )

    value_numeric: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    value_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    session = relationship("QuestionnaireSession")
    question_variant = relationship("QuestionVariant")

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_variant_id",
            name="uq_session_question",
        ),
        
    )

# Map already-scored numeric values to Hebrew response labels.   
class ResponseValueLabel(Base):
    __tablename__ = "response_value_labels"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_questions.id"),
        nullable=False,
    )

    option_position: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    numeric_value: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    text_male: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    text_female: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    source_sheet: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    source_row: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "question_id",
            "option_position",
            name="uq_response_label_position",
        ),
    )


# Store scoring methods, Hebrew subscales, and interpretation ranges.
class QuestionnaireScoringRule(Base):
    __tablename__ = "questionnaire_scoring_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    test_name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Stable code used to avoid duplicate rules during repeat imports.
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    scoring_method: Mapped[str | None] = mapped_column(String(30), nullable=True)

    subscale_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_he: Mapped[str | None] = mapped_column(Text, nullable=True)

    min_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    range_max: Mapped[float | None] = mapped_column(Float, nullable=True)

    interpretation_he: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_sheet: Mapped[str] = mapped_column(String(50), nullable=False)

    # Optional total-score rule that this interpretation describes.
    parent_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("questionnaire_scoring_rules.id"), nullable=True, index=True
    )

    # Keep rules needing review without applying them to participant scores.
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    __table_args__ = (
        UniqueConstraint(
            "test_name",
            "rule_code",
            name="uq_test_scoring_rule",
        ),
    )


# Link each scoring rule to its questions and preserve Excel question numbering.
class ScoringRuleQuestion(Base):
    __tablename__ = "scoring_rule_questions"

    # The combined primary key prevents adding the same question twice to a rule.
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("questionnaire_scoring_rules.id"), primary_key=True
    )

    question_id: Mapped[int] = mapped_column(
        ForeignKey("canonical_questions.id"), primary_key=True, index=True
    )

    source_question_number: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    
    
