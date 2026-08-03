-- Diamond Education - Database Schema Part 3
-- Groups and Student Groups

CREATE TABLE IF NOT EXISTS public.groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  subject_id UUID NOT NULL REFERENCES public.subjects(id),
  level_id UUID NOT NULL REFERENCES public.levels(id),
  teacher_id UUID REFERENCES auth.users(id),
  description TEXT,
  max_students INTEGER DEFAULT 30,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.student_groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
  joined_at TIMESTAMPTZ DEFAULT NOW(),
  status student_status DEFAULT 'active',
  UNIQUE(student_id, group_id)
);

ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.student_groups ENABLE ROW LEVEL SECURITY;

CREATE POLICY "groups_select_all" ON public.groups FOR SELECT USING (true);
CREATE POLICY "student_groups_select_own" ON public.student_groups FOR SELECT USING (auth.uid() = student_id);
