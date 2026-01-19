# Environment Variables Template

## Backend (.env or Fly Secrets)

```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
SUPABASE_URL=https://poeulzxkjcxeszfcsiks.supabase.co
SUPABASE_KEY=your_service_role_key_here
```

## Frontend (.env.local or Fly Secrets)

```bash
NEXT_PUBLIC_API_URL=https://revipro-backend.fly.dev
```

## Fly.io Deployment Commands

### Backend
```bash
cd backend
fly secrets set ANTHROPIC_API_KEY=sk-ant-api03-...
fly secrets set SUPABASE_URL=https://poeulzxkjcxeszfcsiks.supabase.co
fly secrets set SUPABASE_KEY=your_service_role_key
fly deploy
```

### Frontend
```bash
cd frontend
fly secrets set NEXT_PUBLIC_API_URL=https://revipro-backend.fly.dev
fly deploy
```
