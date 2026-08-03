-- Diamond Education - Database Schema Part 5
-- D'Coin System

CREATE TABLE IF NOT EXISTS public.dcoin_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,
  transaction_type TEXT NOT NULL,
  reason TEXT,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.dcoin_balances (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  balance INTEGER DEFAULT 0,
  last_updated TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.dcoin_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dcoin_balances ENABLE ROW LEVEL SECURITY;

CREATE POLICY "dcoin_transactions_select_own" ON public.dcoin_transactions FOR SELECT USING (auth.uid() = student_id);
CREATE POLICY "dcoin_balances_select_own" ON public.dcoin_balances FOR SELECT USING (auth.uid() = student_id);
