CREATE OR REPLACE FUNCTION book_flight_slot(
    p_student_id UUID,
    p_instructor_id UUID,
    p_aircraft_id UUID,
    p_start_utc TIMESTAMPTZ,
    p_end_utc TIMESTAMPTZ
) RETURNS UUID AS $$
DECLARE
    v_booking_id UUID;
    v_role user_role;
    v_medical_expiration DATE;
    v_hours_until_inspection NUMERIC;
    v_duration_hours NUMERIC;
BEGIN
    -- 1. Acquire row-level locks on the instructor and aircraft profiles to prevent concurrent race conditions
    PERFORM 1 FROM profiles WHERE id = p_instructor_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Instructor not found';
    END IF;

    SELECT role INTO v_role FROM profiles WHERE id = p_instructor_id;
    IF v_role != 'instructor' THEN
        RAISE EXCEPTION 'Specified profile is not an instructor';
    END IF;

    -- Lock and fetch aircraft inspection metrics
    SELECT hours_until_inspection INTO v_hours_until_inspection 
    FROM aircraft WHERE id = p_aircraft_id FOR UPDATE;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Aircraft not found';
    END IF;

    -- Validate student existence
    PERFORM 1 FROM profiles WHERE id = p_student_id;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Student not found';
    END IF;

    -- 2. Compliance Check: Medical Certificate
    SELECT medical_expiration_date INTO v_medical_expiration 
    FROM profiles WHERE id = p_student_id;
    IF v_medical_expiration IS NULL OR v_medical_expiration < CURRENT_DATE THEN
        RAISE EXCEPTION 'Compliance Failure: Student medical certificate is expired or missing.';
    END IF;

    -- 3. Compliance Check: Predictive Maintenance
    v_duration_hours := EXTRACT(EPOCH FROM (p_end_utc - p_start_utc)) / 3600.0;
    IF v_duration_hours > v_hours_until_inspection THEN
        RAISE EXCEPTION 'Safety Lockout: Aircraft requires maintenance and does not have enough hours remaining for this flight.';
    END IF;

    -- 4. Overlap Checks
    -- Instructor overlap check
    IF EXISTS (
        SELECT 1 FROM bookings 
        WHERE instructor_id = p_instructor_id 
          AND status = 'active'
          AND start_utc < p_end_utc 
          AND end_utc > p_start_utc
    ) THEN
        RAISE EXCEPTION 'Instructor is already booked for this time';
    END IF;

    -- Aircraft overlap check
    IF EXISTS (
        SELECT 1 FROM bookings 
        WHERE aircraft_id = p_aircraft_id 
          AND status = 'active'
          AND start_utc < p_end_utc 
          AND end_utc > p_start_utc
    ) THEN
        RAISE EXCEPTION 'Aircraft is already booked for this time';
    END IF;

    -- Student overlap check
    IF EXISTS (
        SELECT 1 FROM bookings 
        WHERE student_id = p_student_id 
          AND status = 'active'
          AND start_utc < p_end_utc 
          AND end_utc > p_start_utc
    ) THEN
        RAISE EXCEPTION 'Student is already flying during this time';
    END IF;

    -- 5. Insert and return
    INSERT INTO bookings (student_id, instructor_id, aircraft_id, start_utc, end_utc, status)
    VALUES (p_student_id, p_instructor_id, p_aircraft_id, p_start_utc, p_end_utc, 'active')
    RETURNING id INTO v_booking_id;

    RETURN v_booking_id;
END;
$$ LANGUAGE plpgsql;
