"""Initial schema with all tables and indexes

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('github_id', sa.BigInteger(), nullable=False, unique=True),
        sa.Column('github_login', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('avatar_url', sa.String(length=500), nullable=True),
        sa.Column('plan', sa.String(length=20), server_default='free'),
        sa.Column('stripe_customer_id', sa.String(length=255), nullable=True),
        sa.Column('questions_used_this_month', sa.Integer(), server_default='0'),
        sa.Column('pr_reviews_used_this_month', sa.Integer(), server_default='0'),
        sa.Column('usage_reset_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_check_constraint('ck_users_plan', 'users', "plan IN ('free', 'pro', 'team')")
    
    # Create repositories table
    op.create_table(
        'repositories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('github_repo_id', sa.BigInteger(), nullable=False),
        sa.Column('github_installation_id', sa.BigInteger(), nullable=False),
        sa.Column('owner', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=False),
        sa.Column('default_branch', sa.String(length=100), server_default='main'),
        sa.Column('private', sa.Boolean(), server_default='true'),
        sa.Column('detected_framework', sa.String(length=50), server_default='laravel'),
        sa.Column('framework_version', sa.String(length=20), nullable=True),
        sa.Column('index_status', sa.String(length=20), server_default='pending'),
        sa.Column('index_error', sa.Text(), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(), nullable=True),
        sa.Column('last_indexed_commit', sa.String(length=40), nullable=True),
        sa.Column('file_count', sa.Integer(), server_default='0'),
        sa.Column('symbol_count', sa.Integer(), server_default='0'),
        sa.Column('route_count', sa.Integer(), server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('user_id', 'github_repo_id', name='uq_repos_user_github'),
    )
    op.create_check_constraint('ck_repos_index_status', 'repositories', "index_status IN ('pending', 'cloning', 'indexing', 'ready', 'failed')")
    op.create_index('idx_repos_user', 'repositories', ['user_id'], postgresql_where=sa.text('deleted_at IS NULL'))
    
    # Create files table
    op.create_table(
        'files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('path', sa.String(length=1000), nullable=False),
        sa.Column('sha', sa.String(length=40), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('size_bytes', sa.Integer(), nullable=True),
        sa.Column('last_indexed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('repo_id', 'path', name='uq_files_repo_path'),
    )
    op.create_index('idx_files_repo', 'files', ['repo_id'])
    op.create_index('idx_files_path_trgm', 'files', ['path'], postgresql_using='gin', postgresql_ops={'path': 'gin_trgm_ops'})
    
    # Create symbols table
    op.create_table(
        'symbols',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('files.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('qualified_name', sa.String(length=500), nullable=True),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('signature', sa.Text(), nullable=True),
        sa.Column('docstring', sa.Text(), nullable=True),
        sa.Column('parent_symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id'), nullable=True),
        sa.Column('visibility', sa.String(length=20), nullable=True),
        sa.Column('is_static', sa.Boolean(), server_default='false'),
        sa.Column('search_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_symbols_kind', 'symbols', "kind IN ('class', 'trait', 'interface', 'function', 'method', 'constant')")
    op.create_index('idx_symbols_repo', 'symbols', ['repo_id'])
    op.create_index('idx_symbols_file', 'symbols', ['file_id'])
    op.create_index('idx_symbols_kind', 'symbols', ['repo_id', 'kind'])
    op.create_index('idx_symbols_name_trgm', 'symbols', ['name'], postgresql_using='gin', postgresql_ops={'name': 'gin_trgm_ops'})
    op.create_index('idx_symbols_qualified_trgm', 'symbols', ['qualified_name'], postgresql_using='gin', postgresql_ops={'qualified_name': 'gin_trgm_ops'})
    op.create_index('idx_symbols_search', 'symbols', [sa.text("to_tsvector('simple', COALESCE(search_text, ''))")], postgresql_using='gin')
    
    # Create routes table
    op.create_table(
        'routes',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('uri', sa.String(length=500), nullable=False),
        sa.Column('full_uri', sa.String(length=500), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('controller', sa.String(length=255), nullable=True),
        sa.Column('action', sa.String(length=255), nullable=True),
        sa.Column('handler_type', sa.String(length=20), nullable=True),
        sa.Column('middleware', postgresql.JSONB, server_default='[]'),
        sa.Column('group_prefix', sa.String(length=255), nullable=True),
        sa.Column('group_middleware', postgresql.JSONB, server_default='[]'),
        sa.Column('source_file', sa.String(length=1000), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=True),
        sa.Column('controller_symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_routes_handler_type', 'routes', "handler_type IN ('controller', 'closure', 'invokable')")
    op.create_index('idx_routes_repo', 'routes', ['repo_id'])
    op.create_index('idx_routes_uri', 'routes', ['repo_id', 'full_uri'])
    op.create_index('idx_routes_controller', 'routes', ['repo_id', 'controller'])
    
    # Create migrations table
    op.create_table(
        'migrations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('migration_order', sa.Integer(), nullable=True),
        sa.Column('table_name', sa.String(length=255), nullable=True),
        sa.Column('operation', sa.String(length=20), nullable=True),
        sa.Column('columns', postgresql.JSONB, server_default='[]'),
        sa.Column('indexes', postgresql.JSONB, server_default='[]'),
        sa.Column('foreign_keys', postgresql.JSONB, server_default='[]'),
        sa.Column('is_destructive', sa.Boolean(), server_default='false'),
        sa.Column('destructive_operations', postgresql.JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_migrations_operation', 'migrations', "operation IN ('create', 'alter', 'drop', 'rename')")
    op.create_index('idx_migrations_repo', 'migrations', ['repo_id'])
    op.create_index('idx_migrations_table', 'migrations', ['repo_id', 'table_name'])
    
    # Create models table
    op.create_table(
        'models',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id'), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('table_name', sa.String(length=255), nullable=True),
        sa.Column('fillable', postgresql.JSONB, server_default='[]'),
        sa.Column('guarded', postgresql.JSONB, server_default='[]'),
        sa.Column('casts', postgresql.JSONB, server_default='{}'),
        sa.Column('relationships', postgresql.JSONB, server_default='[]'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_models_repo', 'models', ['repo_id'])
    
    # Create answers table
    op.create_table(
        'answers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('answer_text', sa.Text(), nullable=True),
        sa.Column('answer_sections', postgresql.JSONB, nullable=True),
        sa.Column('unknowns', postgresql.JSONB, server_default='[]'),
        sa.Column('confidence_tier', sa.String(length=10), nullable=True),
        sa.Column('confidence_factors', postgresql.JSONB, nullable=True),
        sa.Column('validation_passed', sa.Boolean(), server_default='true'),
        sa.Column('validation_errors', postgresql.JSONB, server_default='[]'),
        sa.Column('retrieval_stats', postgresql.JSONB, nullable=True),
        sa.Column('llm_model', sa.String(length=50), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('feedback', sa.String(length=10), nullable=True),
        sa.Column('feedback_comment', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_answers_confidence_tier', 'answers', "confidence_tier IN ('high', 'medium', 'low', 'none')")
    op.create_check_constraint('ck_answers_feedback', 'answers', "feedback IN ('up', 'down')")
    op.create_index('idx_answers_repo', 'answers', ['repo_id'])
    op.create_index('idx_answers_user', 'answers', ['user_id'])
    
    # Create citations table
    op.create_table(
        'citations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('answer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('answers.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_index', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('snippet', sa.String(length=500), nullable=False),
        sa.Column('snippet_sha', sa.String(length=40), nullable=True),
        sa.Column('symbol_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('symbols.id'), nullable=True),
        sa.Column('symbol_name', sa.String(length=255), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('retrieval_source', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint('answer_id', 'file_path', 'start_line', 'end_line', name='uq_citations_answer_location'),
    )
    op.create_index('idx_citations_answer', 'citations', ['answer_id'])
    
    # Create pr_reviews table
    op.create_table(
        'pr_reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('pr_number', sa.Integer(), nullable=False),
        sa.Column('pr_title', sa.String(length=500), nullable=True),
        sa.Column('pr_url', sa.String(length=500), nullable=True),
        sa.Column('head_sha', sa.String(length=40), nullable=True),
        sa.Column('base_sha', sa.String(length=40), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='pending'),
        sa.Column('files_changed', sa.Integer(), server_default='0'),
        sa.Column('findings_count', sa.Integer(), server_default='0'),
        sa.Column('critical_count', sa.Integer(), server_default='0'),
        sa.Column('review_posted', sa.Boolean(), server_default='false'),
        sa.Column('github_review_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('repo_id', 'pr_number', 'head_sha', name='uq_pr_reviews_repo_pr_sha'),
    )
    op.create_check_constraint('ck_pr_reviews_status', 'pr_reviews', "status IN ('pending', 'analyzing', 'completed', 'failed')")
    op.create_index('idx_pr_reviews_repo', 'pr_reviews', ['repo_id'])
    
    # Create pr_findings table
    op.create_table(
        'pr_findings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('pr_review_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('pr_reviews.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=True),
        sa.Column('end_line', sa.Integer(), nullable=True),
        sa.Column('evidence', postgresql.JSONB, nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('suggested_fix', sa.Text(), nullable=True),
        sa.Column('comment_posted', sa.Boolean(), server_default='false'),
        sa.Column('github_comment_id', sa.BigInteger(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='open'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_pr_findings_severity', 'pr_findings', "severity IN ('critical', 'warning', 'info')")
    op.create_check_constraint('ck_pr_findings_category', 'pr_findings', "category IN ('secret_exposure', 'migration_destructive', 'auth_middleware_removed', 'dependency_changed', 'env_leaked', 'private_key_exposed')")
    op.create_check_constraint('ck_pr_findings_status', 'pr_findings', "status IN ('open', 'resolved', 'ignored', 'false_positive')")
    op.create_index('idx_findings_pr', 'pr_findings', ['pr_review_id'])
    op.create_index('idx_findings_severity', 'pr_findings', ['repo_id', 'severity'])
    
    # Create usage_events table
    op.create_table(
        'usage_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('embedding_tokens', sa.Integer(), server_default='0'),
        sa.Column('input_tokens', sa.Integer(), server_default='0'),
        sa.Column('output_tokens', sa.Integer(), server_default='0'),
        sa.Column('estimated_cost_micro_cents', sa.Integer(), server_default='0'),
        sa.Column('metadata', postgresql.JSONB, server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_check_constraint('ck_usage_events_type', 'usage_events', "event_type IN ('repo_indexed', 'question_asked', 'pr_reviewed', 'snippet_fetched')")
    op.create_index('idx_usage_user', 'usage_events', ['user_id'])
    op.create_index('idx_usage_date', 'usage_events', ['created_at'])
    
    # Create snippet_cache table
    op.create_table(
        'snippet_cache',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('repo_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('repositories.id', ondelete='CASCADE'), nullable=False),
        sa.Column('file_path', sa.String(length=1000), nullable=False),
        sa.Column('commit_sha', sa.String(length=40), nullable=False),
        sa.Column('start_line', sa.Integer(), nullable=False),
        sa.Column('end_line', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('repo_id', 'commit_sha', 'file_path', 'start_line', 'end_line', name='uq_snippet_cache_location'),
    )
    op.create_index('idx_snippet_cache_expiry', 'snippet_cache', ['expires_at'])


def downgrade() -> None:
    op.drop_table('snippet_cache')
    op.drop_table('usage_events')
    op.drop_table('pr_findings')
    op.drop_table('pr_reviews')
    op.drop_table('citations')
    op.drop_table('answers')
    op.drop_table('models')
    op.drop_table('migrations')
    op.drop_table('routes')
    op.drop_table('symbols')
    op.drop_table('files')
    op.drop_table('repositories')
    op.drop_table('users')
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute('DROP EXTENSION IF EXISTS pg_trgm')

