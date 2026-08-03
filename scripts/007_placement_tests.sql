-- Diamond Education - Database Schema Part 7
-- Placement Tests

CREATE TABLE IF NOT EXISTS public.placement_tests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  subject_id UUID NOT NULL REFERENCES public.subjects(id),
  test_date TIMESTAMPTZ DEFAULT NOW(),
  score INTEGER,
  max_score INTEGER DEFAULT 100,
  level_assigned UUID REFERENCES public.levels(id),
  status TEXT DEFAULT 'completed',
  notes TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.placement_tests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "placement_tests_select_own" ON public.placement_tests FOR SELECT USING (auth.uid() = student_id);
