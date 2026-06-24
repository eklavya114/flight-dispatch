-- Step 1: Create Enums
CREATE TYPE user_role AS ENUM ('student', 'instructor', 'admin');
CREATE TYPE booking_status AS ENUM ('active', 'cancelled');

-- Step 2: Create Tables
CREATE TABLE profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    role user_role DEFAULT 'student',
    medical_expiration_date DATE NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE aircraft (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tail_number TEXT UNIQUE NOT NULL,
    model TEXT NOT NULL,
    flight_hours_total NUMERIC DEFAULT 0,
    hours_until_inspection NUMERIC DEFAULT 100,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID REFERENCES profiles(id),
    instructor_id UUID REFERENCES profiles(id),
    aircraft_id UUID REFERENCES aircraft(id),
    start_utc TIMESTAMPTZ NOT NULL,
    end_utc TIMESTAMPTZ NOT NULL,
    status booking_status DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Step 3: Enable Row-Level Security (RLS)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE aircraft ENABLE ROW LEVEL SECURITY;
ALTER TABLE bookings ENABLE ROW LEVEL SECURITY;

-- Step 4: Write and Apply RLS Policies

-- Profiles policies
CREATE POLICY "Allow authenticated read on profiles" 
    ON profiles FOR SELECT 
    TO authenticated 
    USING (true);

-- Allow users to update their own profiles (excluding role modification) or admins to update any profiles.
CREATE POLICY "Allow users to update own profile except role or admin update all"
    ON profiles FOR UPDATE
    TO authenticated
    USING (
        auth.uid() = id 
        OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    )
    WITH CHECK (
        (
            auth.uid() = id 
            AND role = (SELECT role FROM profiles WHERE id = auth.uid()) -- prevents changing the role column
        )
        OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

-- Aircraft policies
CREATE POLICY "Allow authenticated read on aircraft" 
    ON aircraft FOR SELECT 
    TO authenticated 
    USING (true);

CREATE POLICY "Allow admin to insert aircraft"
    ON aircraft FOR INSERT
    TO authenticated
    WITH CHECK ((SELECT role FROM profiles WHERE id = auth.uid()) = 'admin');

CREATE POLICY "Allow admin to update aircraft"
    ON aircraft FOR UPDATE
    TO authenticated
    USING ((SELECT role FROM profiles WHERE id = auth.uid()) = 'admin')
    WITH CHECK ((SELECT role FROM profiles WHERE id = auth.uid()) = 'admin');

CREATE POLICY "Allow admin to delete aircraft"
    ON aircraft FOR DELETE
    TO authenticated
    USING ((SELECT role FROM profiles WHERE id = auth.uid()) = 'admin');

-- Bookings policies
CREATE POLICY "Allow authenticated read on bookings" 
    ON bookings FOR SELECT 
    TO authenticated 
    USING (true);

CREATE POLICY "Allow student to insert bookings for self"
    ON bookings FOR INSERT
    TO authenticated
    WITH CHECK (student_id = auth.uid());

CREATE POLICY "Allow update for booking owner, instructor, or admin"
    ON bookings FOR UPDATE
    TO authenticated
    USING (
        student_id = auth.uid()
        OR instructor_id = auth.uid()
        OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    )
    WITH CHECK (
        student_id = auth.uid()
        OR instructor_id = auth.uid()
        OR (SELECT role FROM profiles WHERE id = auth.uid()) = 'admin'
    );

-- Delete policy (intentionally omitted to prevent hard-delete)


-- Step 5: Insert Dummy Data (2 instructors, 2 aircraft)
-- Insert aircraft
INSERT INTO aircraft (id, tail_number, model, flight_hours_total, hours_until_inspection)
VALUES 
    ('a0eae848-1b29-45be-968b-5778a3c8cd4e', 'N172HA', 'Cessna 172S', 1250.5, 45.2),
    ('b0eae848-2b29-45be-968b-5778a3c8cd4f', 'N739FS', 'Piper PA-28 Archer', 890.2, 78.8);

-- Since profiles reference auth.users, in a real database migration we need matching records in auth.users.
-- Note: Depending on your schema triggers, inserting into auth.users might trigger automatic profile creation.
-- The statements below assume manual synchronization.
INSERT INTO auth.users (id, email, encrypted_password, email_confirmed_at, role, aud)
VALUES 
    ('c0eae848-3b29-45be-968b-5778a3c8cd50', 'amelia.hart@example.com', '', NOW(), 'authenticated', 'authenticated'),
    ('d0eae848-4b29-45be-968b-5778a3c8cd51', 'marcus.lee@example.com', '', NOW(), 'authenticated', 'authenticated')
ON CONFLICT (id) DO NOTHING;

INSERT INTO profiles (id, full_name, role)
VALUES 
    ('c0eae848-3b29-45be-968b-5778a3c8cd50', 'Amelia Hart', 'instructor'),
    ('d0eae848-4b29-45be-968b-5778a3c8cd51', 'Marcus Lee', 'instructor')
ON CONFLICT (id) DO NOTHING;
