-- Diamond Education - Database Schema Part 2
-- Subjects and Levels

CREATE TABLE IF NOT EXISTS public.subjects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  description TEXT,
  icon TEXT,
  color TEXT,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.levels (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_id UUID NOT NULL REFERENCES public.subjects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  order_index INTEGER NOT NULL,
  description TEXT,
  min_score INTEGER,
  max_score INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default subjects
INSERT INTO public.subjects (name, description, color) VALUES
('English', 'English Language', '#3B82F6'),
('Mathematics', 'Mathematics', '#F59E0B'),
('Science', 'Science', '#10B981')
ON CONFLICT (name) DO NOTHING;

-- Insert default levels for English
INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'A1', 1, 'Beginner' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;

INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'A2', 2, 'Elementary' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;

INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'B1', 3, 'Intermediate' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;

INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'B2', 4, 'Upper Intermediate' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;

INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'C1', 5, 'Advanced' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;

INSERT INTO public.levels (subject_id, name, order_index, description) 
SELECT id, 'C2', 6, 'Proficiency' FROM public.subjects WHERE name = 'English'
ON CONFLICT DO NOTHING;
