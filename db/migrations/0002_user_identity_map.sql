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
