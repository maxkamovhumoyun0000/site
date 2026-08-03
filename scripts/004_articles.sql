-- Diamond Education - Database Schema Part 4
-- Articles and Permissions

CREATE TABLE IF NOT EXISTS public.articles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  content TEXT NOT NULL,
  subject_id UUID NOT NULL REFERENCES public.subjects(id),
  level_id UUID NOT NULL REFERENCES public.levels(id),
  author_id UUID NOT NULL REFERENCES auth.users(id),
  is_published BOOLEAN DEFAULT false,
  visible_to_teachers BOOLEAN DEFAULT true,
  visible_to_support_teachers BOOLEAN DEFAULT false,
  visible_to_students BOOLEAN DEFAULT false,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.articles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "articles_select_published" ON public.articles FOR SELECT USING (is_published = true);
