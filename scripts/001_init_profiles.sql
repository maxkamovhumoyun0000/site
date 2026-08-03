-- Diamond Education - Minimal Database Schema
-- Part 1: Create basic tables

-- User role enum
CREATE TYPE IF NOT EXISTS user_role AS ENUM ('super_admin', 'admin', 'teacher', 'support_teacher', 'student');

-- Student status enum  
CREATE TYPE IF NOT EXISTS student_status AS ENUM ('active', 'inactive', 'graduated', 'suspended');

-- Student type enum
CREATE TYPE IF NOT EXISTS student_type AS ENUM ('regular', 'support');

-- Profiles table (extends auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  full_name TEXT NOT NULL,
  phone TEXT,
  role user_role NOT NULL DEFAULT 'student',
  avatar_url TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "profiles_select_own" ON public.profiles FOR SELECT USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_delete_own" ON public.profiles FOR DELETE USING (auth.uid() = id);
