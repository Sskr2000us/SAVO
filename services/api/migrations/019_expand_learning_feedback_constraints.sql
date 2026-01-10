-- Expand learning_feedback constraint enums
-- Date: 2026-01-09
-- Purpose:
--  - Allow pantry scanning correction events + opt-in learning logs

DO $$
BEGIN
    -- feedback_type
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'learning_feedback_feedback_type_check'
    ) THEN
        ALTER TABLE public.learning_feedback DROP CONSTRAINT learning_feedback_feedback_type_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'learning_feedback_feedback_type_check_v2'
    ) THEN
        ALTER TABLE public.learning_feedback DROP CONSTRAINT learning_feedback_feedback_type_check_v2;
    END IF;

    ALTER TABLE public.learning_feedback
        ADD CONSTRAINT learning_feedback_feedback_type_check_v2
        CHECK (feedback_type IN (
            'cv_confirmation',
            'cv_correction',
            'pantry_vocab_correction',
            'pantry_quantity_correction',
            'substitution_accept',
            'substitution_reject',
            'decision_accept',
            'decision_reject'
        ));

    -- source_entity_type
    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'learning_feedback_source_entity_type_check'
    ) THEN
        ALTER TABLE public.learning_feedback DROP CONSTRAINT learning_feedback_source_entity_type_check;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'learning_feedback_source_entity_type_check_v2'
    ) THEN
        ALTER TABLE public.learning_feedback DROP CONSTRAINT learning_feedback_source_entity_type_check_v2;
    END IF;

    ALTER TABLE public.learning_feedback
        ADD CONSTRAINT learning_feedback_source_entity_type_check_v2
        CHECK (source_entity_type IN (
            'visual_scan_result',
            'ingredient_substitution',
            'ingredient_action',
            'detected_ingredient',
            'inventory_item'
        ));
END $$;
