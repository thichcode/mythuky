-- PostgreSQL schema for memory, feedback, and audit.

create table if not exists schema_migration (
  version text primary key,
  applied_at timestamptz not null default now()
);

create table if not exists chat_session (
  id bigserial primary key,
  thread_id text not null,
  channel text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists webhook_event (
  id bigserial primary key,
  external_event_id text not null unique,
  channel text not null,
  thread_id text not null,
  request_id text not null,
  created_at timestamptz not null default now()
);

create table if not exists memory_short_term (
  id bigserial primary key,
  session_id bigint not null references chat_session(id) on delete cascade,
  request_id text not null,
  key text not null,
  value_json jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_memory_short_term_session on memory_short_term(session_id);

create table if not exists memory_long_term (
  id bigserial primary key,
  scope_type text not null check (scope_type in ('service', 'team', 'user')),
  scope_key text not null,
  key text not null,
  value_json jsonb not null,
  confidence numeric(4,3) not null default 0.500,
  source text not null,
  updated_at timestamptz not null default now(),
  unique(scope_type, scope_key, key)
);

create table if not exists evidence_snapshot (
  id bigserial primary key,
  request_id text not null,
  tool_name text not null,
  payload_json jsonb not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_evidence_request on evidence_snapshot(request_id);

create table if not exists policy_decision_log (
  id bigserial primary key,
  request_id text not null,
  action_type text not null,
  env text not null,
  allowed boolean not null,
  requires_approval boolean not null,
  reason text,
  created_at timestamptz not null default now()
);

create table if not exists action_execution_log (
  id bigserial primary key,
  request_id text not null,
  action_type text not null,
  target text not null,
  idempotency_key text not null,
  status text not null check (status in ('pending_approval', 'approved', 'executed', 'rejected', 'failed')),
  metadata_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(idempotency_key)
);

create table if not exists feedback_event (
  id bigserial primary key,
  request_id text not null,
  user_id text not null,
  feedback_type text not null check (feedback_type in ('approve', 'edit', 'reject')),
  edited_plan_json jsonb,
  rationale text,
  created_at timestamptz not null default now()
);

create table if not exists learning_candidate (
  id bigserial primary key,
  candidate_type text not null check (candidate_type in ('policy', 'retrieval', 'prompt', 'runbook')),
  source_feedback_ids bigint[] not null,
  proposal_json jsonb not null,
  status text not null default 'proposed' check (status in ('proposed', 'approved', 'rejected', 'deployed')),
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create table if not exists user_identity_map (
  id bigserial primary key,
  internal_user_id text not null,
  provider text not null check (provider in ('teams', 'telegram')),
  provider_user_id text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(provider, provider_user_id),
  unique(internal_user_id, provider)
);
