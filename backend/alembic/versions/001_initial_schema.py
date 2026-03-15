"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "labs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("estimated_minutes", sa.Integer, nullable=False),
        sa.Column("objectives", postgresql.JSONB, nullable=False),
        sa.Column("theory_content", sa.Text, nullable=False),
        sa.Column("instructions", postgresql.JSONB, nullable=False),
        sa.Column("initial_topology", postgresql.JSONB, nullable=False),
        sa.Column("verification_rules", postgresql.JSONB, nullable=False),
        sa.Column("prerequisites", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "topologies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("topology_data", postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "lab_id", "name", name="uq_topology_user_lab_name"),
    )

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topology_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topologies.id", ondelete="CASCADE")),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("x", sa.Float, nullable=False, server_default="0"),
        sa.Column("y", sa.Float, nullable=False, server_default="0"),
        sa.Column("configuration", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topology_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topologies.id", ondelete="CASCADE")),
        sa.Column("source_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE")),
        sa.Column("target_device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE")),
        sa.Column("source_interface", sa.String(50), nullable=False),
        sa.Column("target_interface", sa.String(50), nullable=False),
        sa.Column("link_type", sa.String(50), nullable=False, server_default="ethernet"),
        sa.Column("bandwidth_mbps", sa.Integer, server_default="1000"),
        sa.Column("configuration", postgresql.JSONB, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("topology_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("topologies.id", ondelete="CASCADE")),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("results", postgresql.JSONB),
        sa.Column("verification_results", postgresql.JSONB),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "progress",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("lab_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("labs.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(20), nullable=False, server_default="not_started"),
        sa.Column("current_step", sa.Integer, server_default="0"),
        sa.Column("objectives_completed", postgresql.JSONB, server_default=sa.text("'[]'::jsonb")),
        sa.Column("score", sa.Integer, server_default="0"),
        sa.Column("attempts", sa.Integer, server_default="0"),
        sa.Column("best_score", sa.Integer, server_default="0"),
        sa.Column("time_spent_seconds", sa.Integer, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "lab_id", name="uq_progress_user_lab"),
    )

    op.create_index("idx_topologies_user_lab", "topologies", ["user_id", "lab_id"])
    op.create_index("idx_devices_topology", "devices", ["topology_id"])
    op.create_index("idx_connections_topology", "connections", ["topology_id"])
    op.create_index("idx_simulations_user", "simulations", ["user_id"])
    op.create_index("idx_simulations_lab", "simulations", ["lab_id"])
    op.create_index("idx_progress_user", "progress", ["user_id"])
    op.create_index("idx_progress_lab", "progress", ["lab_id"])


def downgrade() -> None:
    op.drop_table("progress")
    op.drop_table("simulations")
    op.drop_table("connections")
    op.drop_table("devices")
    op.drop_table("topologies")
    op.drop_table("labs")
    op.drop_table("users")
