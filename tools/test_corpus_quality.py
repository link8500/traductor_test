"""Measurement regression checks; no model inference or chapter approval."""
import unittest

from audit_corpus_quality import distributed_semantic_comparison, uniform_semantic_comparison, expanded_semantic_comparison, extended_semantic_comparison, coverage_semantic_comparison, six_region_semantic_comparison, six_region_coverage_comparison, full_recovery_checkpoint_comparison, latest_windows_diagnostics, reduction
from translation_quality_signals import signals


class QualitySignalsTest(unittest.TestCase):
    def check(self, source, translation):
        return signals(dict(source=source, translation=translation))

    def test_ordinary_punctuation_and_names_are_not_corrupt_words(self):
        result = self.check('Rhea & Tomas, pay $15!', 'Rhea y Tomas, ¡paguen $15!')
        self.assertNotIn('malformed_source', result)
        self.assertNotIn('malformed_output', result)

    def test_attached_and_internal_corruption_are_both_detected(self):
        for text in ['ROCK&', 'DREA&ER', '{DREAMER', 'DRE4MER']:
            with self.subTest(text=text):
                result = self.check(text, text)
                self.assertIn('malformed_source', result)
                self.assertIn('malformed_output', result)

    def test_english_phrases_survive_accented_spanish_context(self):
        for text in ["Después, I'm returning.", 'Eso fue in the garden.', '¿Are you preparado?']:
            with self.subTest(text=text):
                self.assertIn('english_phrase_output', self.check('A source sentence.', text))

    def test_repetition_is_not_a_two_word_stutter(self):
        self.assertNotIn('repeated_output', self.check('Stop.', 'No, no, espera.'))
        self.assertIn('repeated_output', self.check('Wait for me.', 'Espera aquí espera aquí espera aquí espera aquí.'))

    def test_negation_is_a_risk_signal_not_a_semantic_verdict(self):
        self.assertIn('possible_lost_negation', self.check('We will get there without any delay.', 'Llegaremos puntualmente.'))
        self.assertNotIn('possible_lost_negation', self.check('We will not go to that place.', 'No iremos a ese lugar.'))

    def test_stylized_case_corruption_but_not_short_brand_names(self):
        self.assertIn('mixed_case_source', self.check('WuVoqErWr travels.', 'WuVoqErWr viaja.'))
        self.assertNotIn('mixed_case_source', self.check('Use iPhone with WiFi.', 'Usa iPhone con WiFi.'))

    def test_missing_output_is_still_flagged_on_a_credit(self):
        self.assertIn('missing_output', self.check('TRANSLATOR CREDITS', ''))

    def test_short_unresolved_tokens_are_not_lost_but_remain_unconfirmed(self):
        self.assertIn('unresolved_copied_token', self.check('The XQZ was broken.', 'El XQZ estaba roto.'))
        self.assertNotIn('unresolved_copied_token', self.check('The radio was broken.', 'La radio estaba rota.'))

    def test_reduction_is_relative_and_can_be_negative(self):
        self.assertEqual(reduction(100, 80), 20)
        self.assertEqual(reduction(10, 12), -20)
        self.assertIsNone(reduction(0, 0))

    def test_real_frozen_sample_keeps_exclusions_and_regressions(self):
        report = distributed_semantic_comparison()
        self.assertEqual(report['reviewed_regions'], 124)
        self.assertEqual(report['comparable_regions'], 122)
        self.assertEqual(report['excluded_unresolved_regions'], 2)
        self.assertEqual(report['before_errors']-report['after_errors'],
                         report['corrected_regions']-report['regressed_regions'])
        self.assertGreater(report['regressed_regions'], 0)
        self.assertFalse(report['population_accuracy_estimate'])
        self.assertFalse(report['single_latest_build_comparison'])

    def test_uniform_review_preserves_same_version_and_all_outcomes(self):
        report = uniform_semantic_comparison()
        self.assertEqual(report['chapters_sampled'], 124)
        self.assertEqual(report['reviewed_regions'], 372)
        self.assertEqual(report['reviewed_regions'], report['comparable_regions']+report['excluded_unresolved_regions'])
        self.assertEqual(report['before_errors']-report['after_errors'], report['corrected_regions']-report['regressed_regions'])
        self.assertEqual(report['reused_identical_output_judgments']+report['changed_outputs_visually_reinspected'],372)
        self.assertTrue(report['single_build_comparison'])
        self.assertFalse(report['population_accuracy_estimate'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])

    def test_expanded_review_keeps_short_regions_and_false_detection_exclusion(self):
        report=expanded_semantic_comparison()
        self.assertEqual(report['reviewed_regions'],496)
        self.assertEqual(report['comparable_regions'],488)
        self.assertEqual(report['excluded_unresolved_regions'],8)
        self.assertEqual(report['before_errors']-report['after_errors'],report['corrected_regions']-report['regressed_regions'])
        self.assertEqual(report['newly_inspected_short_regions'],124)
        self.assertTrue(report['single_build_comparison'])
        self.assertFalse(report['population_accuracy_estimate'])

    def test_additional_review_preserves_previous_evidence_and_new_regressions(self):
        previous=expanded_semantic_comparison();current=extended_semantic_comparison()
        self.assertEqual(current['reviewed_regions']-previous['reviewed_regions'],124)
        self.assertEqual(current['comparable_regions'],612)
        self.assertEqual(current['excluded_unresolved_regions'],8)
        self.assertEqual(current['before_errors']-current['after_errors'],current['corrected_regions']-current['regressed_regions'])
        self.assertEqual(current['regressed_regions']-previous['regressed_regions'],5)
        self.assertTrue(current['single_build_comparison'])
        self.assertFalse(current['population_accuracy_estimate'])

    def test_sentence_coverage_preserves_the_same_exclusions_and_unchanged_judgments(self):
        previous=extended_semantic_comparison();current=coverage_semantic_comparison()
        self.assertEqual(current['reviewed_regions'],previous['reviewed_regions'])
        self.assertEqual(current['comparable_regions'],previous['comparable_regions'])
        self.assertEqual(current['excluded_unresolved_regions'],previous['excluded_unresolved_regions'])
        self.assertEqual(current['before_errors'],previous['after_errors'])
        self.assertEqual(current['before_errors']-current['after_errors'],current['corrected_regions']-current['regressed_regions'])
        self.assertEqual(current['changed_outputs_visually_reinspected']+current['identical_output_judgments_reused'],620)
        self.assertTrue(current['ocr_pixels_and_source_held_fixed'])
        self.assertFalse(current['translator_weights_changed'])
        self.assertFalse(current['population_accuracy_estimate'])

    def test_sixth_location_adds_comparisons_without_rewriting_the_previous_snapshot(self):
        previous=extended_semantic_comparison();current=six_region_semantic_comparison()
        self.assertEqual(previous['reviewed_regions'],620)
        self.assertEqual(current['reviewed_regions'],744)
        self.assertEqual(current['comparable_regions'],735)
        self.assertEqual(current['excluded_unresolved_regions'],previous['excluded_unresolved_regions']+1)
        self.assertEqual(current['corrected_regions']-previous['corrected_regions'],54)
        self.assertEqual(current['regressed_regions']-previous['regressed_regions'],2)
        self.assertFalse(current['all_chapter_words_visually_reviewed'])

    def test_enlarged_native_trial_keeps_exclusions_and_separates_the_historical_baseline(self):
        previous=six_region_semantic_comparison();current=six_region_coverage_comparison()
        self.assertEqual(current['comparable_regions'],previous['comparable_regions'])
        self.assertEqual(current['excluded_unresolved_regions'],previous['excluded_unresolved_regions'])
        self.assertEqual(current['before_errors'],203)
        self.assertEqual(current['after_errors'],197)
        self.assertEqual(current['corrected_regions'],6)
        self.assertEqual(current['regressed_regions'],0)
        historical=current['historical_baseline_comparison']
        self.assertEqual(historical['before_errors'],491)
        self.assertEqual(historical['after_errors'],current['after_errors'])
        self.assertEqual(historical['before_errors']-historical['after_errors'],historical['corrected_regions']-historical['regressed_regions'])
        self.assertFalse(current['translator_weights_changed'])

    def test_partial_ocr_checkpoint_does_not_become_a_whole_corpus_approval(self):
        current=full_recovery_checkpoint_comparison()
        self.assertEqual(current['reviewed_regions'],318)
        self.assertEqual(current['comparable_regions'],314)
        self.assertEqual(current['excluded_unresolved_regions'],4)
        self.assertEqual(current['before_errors']-current['after_errors'],current['corrected_regions']-current['regressed_regions'])
        self.assertEqual(current['changed_outputs_visually_reinspected']+current['identical_output_judgments_reused'],318)
        self.assertTrue(current['partial_full_chapter_ocr_checkpoint'])
        self.assertTrue(current['overlaps_with_main_sample_do_not_add_counts'])
        self.assertFalse(current['all_chapter_words_visually_reviewed'])

    def test_screen_failure_goal_does_not_use_a_word_average(self):
        report=latest_windows_diagnostics();policy=report['screen_acceptance']
        self.assertEqual(policy['measurement_unit'],'one_complete_screen_translation_attempt')
        self.assertEqual(policy['target_failure_probability_strictly_below'],.05)
        self.assertIsNone(policy['current_screen_attempt_failure_probability'])
        self.assertFalse(policy['partial_region_reviews_can_approve_a_screen'])
        self.assertFalse(policy['target_achieved'])

    def test_omission_trial_revisions_and_selected_diagnostic_stay_separate(self):
        report=latest_windows_diagnostics();fixed=report['omission_candidate'];full=report['full_omission']
        self.assertEqual(len(fixed['explicit_historical_judgment_corrections']),2)
        self.assertEqual(fixed['before_errors'],199)
        self.assertEqual(fixed['after_errors'],196)
        self.assertEqual(full['reviewed_regions'],37)
        self.assertEqual(full['before_errors']-full['after_errors'],full['corrected_regions']-full['regressed_regions'])
        self.assertTrue(full['all_changed_regions_semantically_reviewed'])
        self.assertFalse(full['unchanged_region_meaning_reviewed'])
        self.assertTrue(full['changed_candidates_only'])
        self.assertIsNone(full['screen_attempt_failure_probability'])

    def test_heldout_consensus_does_not_approve_unchanged_unreviewed_crops(self):
        report=latest_windows_diagnostics();development=report['ocr_consensus_development'];heldout=report['ocr_consensus_heldout']
        self.assertEqual(development['before_crops_with_error'],34)
        self.assertEqual(development['after_crops_with_error'],19)
        self.assertEqual(heldout['changed_locations_visually_reviewed'],12)
        self.assertEqual(heldout['unchanged_locations_without_meaning_approval'],112)
        self.assertEqual(heldout['changed_crops_still_have_word_errors'],2)
        self.assertEqual(heldout['changed_crops_regressed'],0)
        self.assertTrue(heldout['rule_frozen_before_location_selection'])
        self.assertFalse(heldout['application_modified'])

    def test_extended_heldout_review_counts_unchanged_errors_and_keeps_screen_rate_unknown(self):
        report=latest_windows_diagnostics();expanded=report['ocr_consensus_heldout_full']
        self.assertEqual(expanded['crops_visually_reviewed'],124)
        self.assertEqual(expanded['additional_unchanged_crops_reviewed'],112)
        models=expanded['cohorts']['all_124_including_clipped_edges']['models']
        self.assertEqual(models['conservative_consensus']['crops_with_word_error'],24)
        self.assertEqual(models['conservative_consensus']['edit_categories']['omitted_word'],6)
        self.assertEqual(models['current']['crops_with_word_error']-models['conservative_consensus']['crops_with_word_error'],
            models['conservative_consensus']['crops_fixed_vs_current']-models['conservative_consensus']['crops_regressed_vs_current'])
        self.assertIsNone(expanded['screen_attempt_failure_probability'])
        self.assertFalse(expanded['all_chapter_words_visually_reviewed'])
        self.assertFalse(expanded['application_modified'])


    def test_new_native_heldout_includes_all_unchanged_outputs_in_strict_count(self):
        report=latest_windows_diagnostics()['windows_heldout']
        cohort=report['cohorts']['all_124_including_clipped_edges']
        self.assertEqual(report['reviewed_locations'],124)
        self.assertEqual(cohort['before_not_approved'],45)
        self.assertEqual(cohort['after_not_approved'],44)
        self.assertEqual(cohort['after_not_approved'],cohort['after_clear_errors']+cohort['after_categories']['needs_improvement'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['population_accuracy_estimate'])

    def test_geometry_review_keeps_old_readings_and_reuses_only_identical_results(self):
        report=latest_windows_diagnostics()['geometry_trial']
        cohort=report['cohorts']['all_124_including_clipped_edges']
        self.assertEqual(report['changed_locations_reinspected']+report['identical_location_judgments_reused'],124)
        self.assertEqual(cohort['before_not_approved']-cohort['after_not_approved'],cohort['corrected']-cohort['regressed'])
        self.assertTrue(report['all_124_original_source_strings_preserved'])
        self.assertTrue(report['naive_trial_rejected_due_to_recognition_regression'])
        self.assertFalse(report['experimental_ocr_consensus_included'])
        self.assertFalse(report['experimental_short_clause_policy_included'])
        self.assertFalse(report['target_achieved'])

    def test_new_candidate_reports_preserve_unreviewed_and_unshipped_scope(self):
        report=latest_windows_diagnostics()
        ocr=report['ocr_coverage_heldout'];short=report['short_clause_candidate']
        self.assertEqual(ocr['changed_locations_visually_reviewed'],16)
        self.assertEqual(ocr['unchanged_locations_without_meaning_approval'],108)
        self.assertFalse(ocr['application_modified'])
        self.assertEqual(short['reviewed_changed_locations'],14)
        self.assertEqual(short['before_not_approved']-short['after_not_approved'],short['corrected']-short['regressed'])
        self.assertEqual(short['after_not_approved'],5)
        self.assertFalse(short['included_in_application'])
        self.assertFalse(short['all_planned_location_meanings_reviewed'])


    def test_short_clause_application_keeps_partial_fixes_pending(self):
        report=latest_windows_diagnostics()['windows8018_trial'];m=report['cohorts']['all_124_including_clipped_edges']
        self.assertEqual(report['changed_locations_reinspected'],4)
        self.assertEqual(report['identical_location_judgments_reused'],120)
        self.assertEqual(m['before_not_approved'],41)
        self.assertEqual(m['after_not_approved'],39)
        self.assertEqual(m['after_not_approved'],m['after_clear_errors']+m['after_categories']['needs_improvement'])
        self.assertTrue(report['short_clause_recovery_in_application'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_finished_old_control_retains_regression_and_judgment_revision(self):
        report=latest_windows_diagnostics()['older_full_ocr_control'];m=report['metrics']
        self.assertEqual(report['newly_changed_pixel_locations_inspected']+report['prior_changed_pixel_judgments_reused'],99)
        self.assertEqual(report['unchanged_same_location_judgments_reused']+report['changed_locations'],744)
        self.assertEqual(m['comparable_regions']+m['excluded_unresolved_regions'],744)
        self.assertEqual(m['before_not_approved']-m['after_not_approved'],m['corrected']-m['regressed'])
        self.assertEqual(m['regressed'],1)
        self.assertEqual(len(report['explicit_judgment_revisions']),1)
        self.assertFalse(report['current_application_build'])
        self.assertTrue(report['overlaps_with_other_samples_do_not_add'])

    def test_broad_trial_retains_full_and_partial_regressions(self):
        report=latest_windows_diagnostics()['corpus_coverage8018']
        self.assertEqual(report['changed_locations_reviewed'],119)
        self.assertEqual(report['source_locations_scanned'],18179)
        self.assertEqual(report['fully_corrected'],82)
        self.assertEqual(report['full_region_regressions'],1)
        self.assertEqual(report['already_failed_regions_with_partial_content_worsening'],1)
        self.assertFalse(report['unchanged_regions_automatically_approved'])
        self.assertFalse(report['ready_for_release'])

    def test_precision_variant_rejected_without_net_improvement(self):
        report=latest_windows_diagnostics()['int8_trial8018']
        self.assertEqual(report['changed_locations_visually_reviewed'],52)
        self.assertEqual(report['identical_location_judgments_reused'],72)
        self.assertEqual(report['baseline_judgment_revisions'],2)
        self.assertEqual(report['before_not_approved'],41)
        self.assertEqual(report['after_not_approved'],41)
        self.assertEqual(report['fully_corrected'],4)
        self.assertEqual(report['regressed'],4)
        self.assertFalse(report['quantization_variant_accepted_for_deployment'])

    def test_all_remaining_third_ocr_locations_are_counted_including_omissions(self):
        report=latest_windows_diagnostics()['ocr_third_full8019'];m=report['metrics']['strict_apostrophes']
        self.assertEqual(report['crops_visually_reviewed'],124)
        self.assertEqual(report['additional_unchanged_crops_reviewed'],108)
        self.assertEqual(report['negative_control_crops_without_dialogue'],1)
        self.assertEqual(m['before_word_errors'],46)
        self.assertEqual(m['after_word_errors'],27)
        self.assertEqual(m['after_crops_with_word_errors'],19)
        self.assertEqual(report['metrics']['legacy']['after_edit_categories']['omitted_word'],5)
        self.assertFalse(report['meanings_of_spanish_outputs_reviewed'])
        self.assertFalse(report['application_modified'])

    def test_protected_windows_trial_binds_exact_outputs_and_applies_revisions_to_both_sides(self):
        report=latest_windows_diagnostics()['windows8019_trial'];m=report['cohorts']['all_124_including_clipped_edges']
        self.assertTrue(report['all124_meaning_judgments_bound_to_exact_same_location_outputs'])
        self.assertEqual(report['baseline_judgment_revisions'],2)
        self.assertEqual(m['before_not_approved'],43)
        self.assertEqual(m['after_not_approved'],41)
        self.assertEqual(m['corrected'],2)
        self.assertEqual(m['regressed'],0)
        self.assertEqual(report['recoveries_withheld_vs_unguarded_trial'],1)
        self.assertFalse(report['ready_for_release'])

    def test_broad_protection_removes_regressions_without_approving_unchanged_regions(self):
        report=latest_windows_diagnostics()['corpus_coverage8019']
        self.assertEqual(report['fresh_native_validation_sources'],1160)
        self.assertEqual(report['native_guard_plan_disagreements'],0)
        self.assertEqual(report['before_not_approved'],117)
        self.assertEqual(report['after_not_approved'],41)
        self.assertEqual(report['fully_corrected'],76)
        self.assertEqual(report['full_region_regressions'],0)
        self.assertEqual(report['partial_content_worsening_from_rejected_trial_remaining'],0)
        self.assertEqual(report['recoveries_rejected'],16)
        self.assertFalse(report['unchanged_regions_automatically_approved'])
        self.assertIsNone(report['screen_attempt_failure_probability'])

    def test_integrated_reader_trial_stays_disabled_until_broader_validation(self):
        report=latest_windows_diagnostics()['windows8020_trial'];m=report['cohorts']['all_124_including_clipped_edges']
        self.assertEqual(report['changed_locations_reinspected'],7)
        self.assertEqual(report['identical_location_judgments_reused'],117)
        self.assertEqual(m['before_not_approved'],41)
        self.assertEqual(m['after_not_approved'],36)
        self.assertEqual(m['corrected'],5)
        self.assertEqual(m['regressed'],0)
        self.assertFalse(report['live_worker_enabled'])
        self.assertFalse(report['ready_for_release'])


    def test_full_viewport_inventory_is_not_limited_to_detected_boxes(self):
        report=latest_windows_diagnostics()['windows8020_full_viewports']
        self.assertEqual(report['viewports'],124)
        self.assertEqual(report['native_regions'],228)
        self.assertTrue(report['all_original_visible_dialogue_inventoried'])
        self.assertTrue(report['unchanged_full_viewports_independently_reviewed'])
        self.assertFalse(report['judgment_reused_from_crop_cohorts'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertFalse(report['complete_app_use_including_capture_toolbar_and_movement'])

    def test_full_viewport_regression_cannot_be_hidden_by_better_crop_results(self):
        report=latest_windows_diagnostics()['windows8020_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual(m['before_not_approved'],62)
        self.assertEqual(m['after_not_approved'],60)
        self.assertEqual(m['corrected'],3)
        self.assertEqual(m['regressed'],1)
        self.assertEqual(report['cohorts']['no_visible_dialogue_clipped']['viewports'],107)
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['ready_for_release'])

    def test_complete_reading_trial_reverses_regression_without_claiming_full_uses(self):
        report=latest_windows_diagnostics()['windows8021_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports']
        historical=report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual(report['changed_viewports_reinspected'],10)
        self.assertEqual(report['same_full_location_outputs_reused'],114)
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(60,58,2,0))
        self.assertEqual((historical['before_not_approved'],historical['after_not_approved'],historical['corrected'],historical['regressed']),(62,58,4,0))
        self.assertTrue(report['exact_selector_prediction_matches_all228_actual_windows_sources'])
        self.assertFalse(report['default_live_worker_enabled'])
        self.assertFalse(report['complete_app_use_including_capture_toolbar_and_movement'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_rejected_local_model_cannot_replace_current_windows_results(self):
        report=latest_windows_diagnostics()
        trials=report['rejected_local_llm8021_trials']
        self.assertEqual(len(trials),2)
        self.assertEqual([r['cohorts']['all124_fixed_reading_viewports']['after_not_approved'] for r in trials],[85,89])
        for row in trials:
            self.assertTrue(row['all124_new_meanings_reviewed'])
            self.assertTrue(row['native_ocr_sources_and_bounds_all_identical'])
            self.assertFalse(row['provider_accepted_for_deployment'])
            self.assertFalse(row['application_modified'])
            self.assertIsNone(row['screen_attempt_failure_probability'])
        self.assertEqual(report['windows8021_full_viewports']['cohorts']['all124_fixed_reading_viewports']['after_not_approved'],58)

    def test_wider_search_cannot_hide_partial_regressions_or_claim_an_improvement(self):
        report=latest_windows_diagnostics()
        trial=report['rejected_search8022'];m=trial['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual(trial['changed_viewports_reviewed'],12)
        self.assertEqual(trial['identical_full_location_judgments_reused'],112)
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(58,58,0,0))
        self.assertEqual(m['already_failed_views_partially_worsened'],2)
        self.assertEqual(m['relative_unapproved_reduction_percent'],0)
        self.assertFalse(trial['accepted_for_application'])
        self.assertFalse(trial['application_modified'])
        self.assertIsNone(trial['screen_attempt_failure_probability'])
        self.assertFalse(trial['target_achieved'])

    def test_full_dialogue_ocr_does_not_drop_undetected_words_or_certify_app_accuracy(self):
        report=latest_windows_diagnostics()['full_viewport_dialogue_ocr8023']
        m=report['cohorts']['all124_fixed_reading_viewports']['variants']
        self.assertEqual(m['full_consensus']['expected_dialogue_words'],2265)
        self.assertEqual(m['baseline']['word_errors'],80)
        self.assertEqual(m['full_consensus']['word_errors'],48)
        self.assertEqual(m['full_consensus']['viewports_with_word_errors'],24)
        self.assertEqual(m['full_consensus']['alignment_edit_categories']['alignment_deleted_word'],25)
        self.assertEqual(report['dialogue_rows']+report['excluded_non_dialogue_rows'],228)
        self.assertTrue(report['dialogue_is_not_limited_to_detected_boxes'])
        self.assertTrue(report['translation_meaning_not_measured_by_this_report'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_case_normalized_alternative_preserves_input_and_counts_regressions(self):
        trial=latest_windows_diagnostics()['normalized_llm8023']
        m=trial['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(58,74,10,26))
        self.assertTrue(trial['only_user_passage_casing_changed_from_prior_recommended'])
        self.assertTrue(trial['prompt_sampling_model_and_runtime_unchanged'])
        self.assertFalse(trial['candidate_improved_on_this_cohort'])
        self.assertFalse(trial['provider_accepted_for_deployment'])
        self.assertFalse(trial['application_modified'])
        self.assertIsNone(trial['screen_attempt_failure_probability'])

    def test_specialist_comparison_preserves_losses_and_does_not_certify_deployment(self):
        trial=latest_windows_diagnostics()['specialist_hy8024']
        m=trial['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(58,57,15,14))
        self.assertEqual(m['before_not_approved']-m['after_not_approved'],m['corrected']-m['regressed'])
        self.assertTrue(trial['all124_new_meanings_reviewed'])
        self.assertTrue(trial['outputs_not_used_to_train_other_models'])
        self.assertFalse(trial['provider_accepted_for_deployment'])
        self.assertFalse(trial['distribution_approved'])
        self.assertFalse(trial['application_modified'])
        self.assertIsNone(trial['screen_attempt_failure_probability'])

    def test_native_short_dialogue_fix_keeps_the_full_word_denominator(self):
        report=latest_windows_diagnostics()['windows8024_short_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports'];words=report['dialogue_ocr']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(58,57,1,0))
        self.assertEqual((words['before']['expected_dialogue_words'],words['after']['expected_dialogue_words']),(2265,2265))
        self.assertEqual((words['before']['word_errors'],words['after']['word_errors']),(48,47))
        self.assertEqual(report['native_regions'],229)
        self.assertEqual((report['changed_viewports_reviewed'],report['identical_full_location_judgments_reused']),(1,123))
        self.assertEqual(report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']['after_not_approved'],57)
        self.assertFalse(report['default_live_worker_enabled'])
        self.assertIsNone(report['screen_attempt_failure_probability'])

    def test_normal_short_recovery_is_checked_without_enabling_optional_readers(self):
        report=latest_windows_diagnostics()['windows8024_default_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(62,61,1,0))
        self.assertTrue(report['default_short_recovery_enabled'])
        self.assertFalse(report['optional_consensus_readers_enabled'])
        self.assertFalse(report['explicit_short_override_supplied'])
        self.assertEqual(report['identical_full_location_judgments_reused'],123)
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])

    def test_packaged_readers_reproduce_reviewed_outputs_without_special_activation(self):
        report=latest_windows_diagnostics()['windows8025_packaged_full_viewports']
        current=report['cohorts']['all124_fixed_reading_viewports']
        historical=report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((current['before_not_approved'],current['after_not_approved'],current['corrected'],current['regressed']),(61,57,4,0))
        self.assertEqual((historical['before_not_approved'],historical['after_not_approved'],historical['corrected'],historical['regressed']),(62,57,5,0))
        self.assertTrue(report['all124_meaning_judgments_reused_only_for_identical_full_location_outputs'])
        self.assertTrue(report['normal_worker_consensus_enabled'])
        self.assertTrue(report['default_benchmark_consensus_enabled'])
        self.assertTrue(report['no_explicit_reader_paths_or_activation_flag'])
        self.assertEqual(report['reused_dialogue_ocr_component']['all124_fixed_reading_viewports']['after']['word_errors'],47)
        self.assertFalse(report['model_weights_trained'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertFalse(report['complete_live_app_use_including_capture_and_movement'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_inflection_fix_preserves_all_words_and_does_not_certify_app_failure_probability(self):
        report=latest_windows_diagnostics()['windows8026_inflection_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports']
        h=report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(57,57,0,0))
        self.assertEqual((h['before_not_approved'],h['after_not_approved'],h['corrected'],h['regressed']),(62,57,5,0))
        word=report['dialogue_ocr']['all124_fixed_reading_viewports']
        self.assertEqual((word['before']['expected_dialogue_words'],word['after']['expected_dialogue_words']),(2265,2265))
        self.assertEqual((word['before']['word_errors'],word['after']['word_errors']),(47,45))
        self.assertEqual(report['native_guards']['guards'],12)
        self.assertEqual(report['control_crops_unique'],372)
        self.assertTrue(all(not r['worsened'] for r in report['control_crop_cohorts'].values()))
        self.assertEqual((report['changed_full_location_meanings_reviewed'],report['identical_full_location_judgments_reused']),(2,122))
        self.assertEqual(report['partial_content_improvements_not_counted_as_complete_corrections'],2)
        self.assertTrue(report['normal_worker_inflection_support_enabled'])
        self.assertFalse(report['reference_or_manual_answers_supplied_to_app'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertFalse(report['model_weights_trained'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_full_chapter_delta_preserves_duplicate_and_unmatched_regions(self):
        from full_native_delta8026 import pair_same_geometry
        before=[dict(image=0,bounds=[1,2,30,40],source='First'),dict(image=0,bounds=[1,2,30,40],source='Second')]
        after=[dict(image=0,bounds=[1,2,30,40],source='New'),dict(image=1,bounds=[1,2,30,40],source='Other image')]
        pairs,removed,added=pair_same_geometry(before,after)
        self.assertEqual(pairs,[(0,0)])
        self.assertEqual(removed,[1])
        self.assertEqual(added,[1])
        self.assertEqual(pair_same_geometry([],[]),([],[],[]))

    def test_question_restoration_changes_meaning_count_without_claiming_new_ocr(self):
        report=latest_windows_diagnostics()['windows8027_question_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports'];h=report['historical_baseline_comparison']['cohorts']['all124_fixed_reading_viewports']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(57,56,1,0))
        self.assertEqual((h['before_not_approved'],h['after_not_approved'],h['corrected'],h['regressed']),(62,56,6,0))
        self.assertEqual((report['changed_complete_location_meanings_reviewed'],report['identical_complete_location_judgments_reused']),(1,123))
        self.assertEqual(report['native_punctuation_guards']['guards'],20)
        self.assertEqual(report['historical_full_corpus_rows_checked'],18179)
        words=report['dialogue_ocr']['all124_fixed_reading_viewports']
        self.assertEqual((words['before']['word_errors'],words['after']['word_errors']),(45,45))
        self.assertEqual((words['before']['expected_dialogue_words'],words['after']['expected_dialogue_words']),(2265,2265))
        self.assertTrue(report['fresh_translation_inference'])
        self.assertFalse(report['new_ocr_inference'])
        self.assertFalse(report['fresh_screen_capture'])
        self.assertFalse(report['model_weights_trained'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_opening_recovery_keeps_fixed_control_separate_from_diagnostic(self):
        report=latest_windows_diagnostics()['windows8028_opening_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports'];e=report['expanded_opening_diagnostic']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(56,56,0,0))
        self.assertEqual((e['candidates'],e['changed_regions'],e['complete_corrections']),(68,17,11))
        self.assertEqual((e['partial_recoveries_with_confirmed_residual_defects'],e['still_needs_review']),(5,1))
        self.assertEqual(e['after_not_approved'],6)
        self.assertTrue(e['not_added_to_fixed124_counts'])
        self.assertFalse(e['all_unchanged_candidates_meanings_reviewed'])
        self.assertEqual(report['opening_policy_guards']['guards'],28)
        self.assertTrue(report['normal_live_worker_uses_same_opening_rule'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_opening_full_reports_keep_ocr_and_every_unmodified_output(self):
        from audit_corpus_quality import QA,read,records,digest
        import os
        paths=list((QA/'postprocessed-en8028-openings').glob('*.done.json'))
        self.assertGreater(len(paths),0)
        for path in paths:
            value=read(path);base=QA/'postprocessed-en8027-questions'/path.name
            parent=read(base);raw=base.with_name(base.name.replace('.done.json','.jsonl'))
            result=path.with_name(path.name.replace('.done.json','.jsonl'))
            self.assertEqual(value['engine'],parent['engine'])
            self.assertEqual(value['display_build'],'802801')
            self.assertEqual(value['opening_derivation_proof']['parent_report_sha256'],digest(raw))
            self.assertFalse(value['new_ocr_inference'])
            self.assertFalse(value['fresh_translation_for_all_regions'])
            self.assertFalse(value['word_review_complete'])
            before,after=records(raw),records(result)
            self.assertEqual(len(before),len(after))
            changed=0
            for a,b in zip(before,after):
                self.assertEqual((a['image'],a['bounds'],a['source']),(b['image'],b['bounds'],b['source']))
                if a['translation']!=b['translation']:
                    changed+=1
                    self.assertTrue(b['opening_recovered'])
                    self.assertTrue(b['translation'].endswith(' '+a['translation']))
            self.assertEqual(changed,value['openings_recovered'])
            if value['shared_immutable_core_report']:self.assertTrue(os.path.samefile(raw,result))

    def test_refinement_uses_fresh_pixels_without_turning_word_error_into_app_success(self):
        report=latest_windows_diagnostics()['windows8029_refinement_full_viewports']
        m=report['cohorts']['all124_fixed_reading_viewports'];d=report['expanded_refinement_diagnostic']
        self.assertEqual((m['before_not_approved'],m['after_not_approved'],m['corrected'],m['regressed']),(56,56,0,0))
        self.assertEqual((d['changed_physical_locations'],d['complete_corrections'],d['partial_improvements_with_residual_errors']),(7,3,4))
        self.assertTrue(d['counts_not_added_to_fixed_view_results'])
        w=report['dialogue_ocr']['all124_fixed_reading_viewports']
        self.assertEqual((w['before']['word_errors'],w['after']['word_errors']),(45,44))
        self.assertEqual(w['after']['expected_dialogue_words'],2265)
        self.assertTrue(report['fresh_native_ocr'])
        self.assertTrue(report['fresh_translation_inference'])
        self.assertFalse(report['fresh_screen_capture'])
        self.assertEqual(report['actual_native_images'],131)
        self.assertEqual(report['unique_control_crop_pixels'],372)
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_full_refinement_keeps_original_rows_and_frozen_vocabulary(self):
        from audit_corpus_quality import QA,read,records,digest
        import re
        paths=list((QA/'postprocessed-en8029-refinement').glob('*.done.json'));self.assertGreater(len(paths),0)
        vocabulary=QA/'frozen-windows802901/data/flutter_assets/assets/models/opus-en-es/tokenizer.json'
        for path in paths:
            value=read(path);base=QA/'postprocessed-en8028-openings'/path.name
            raw=base.with_name(base.name.replace('.done.json','.jsonl'));target=path.with_name(path.name.replace('.done.json','.jsonl'))
            self.assertEqual(value['refinement_derivation_proof']['parent_report_sha256'],digest(raw))
            self.assertEqual(value['refinement_derivation_proof']['vocabulary_sha256'],digest(vocabulary))
            self.assertFalse(value['new_ocr_inference'])
            self.assertFalse(value['word_review_complete'])
            self.assertFalse(value['fresh_translation_for_all_regions'])
            before,after=records(raw),records(target);self.assertEqual(len(before),len(after))
            for a,b in zip(before,after):
                self.assertEqual((a['image'],a['bounds']),(b['image'],b['bounds']))
                self.assertEqual(len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",a['source'])),len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?",b['source'])))
                if a['source']==b['source'] and a['translation']!=b['translation']:
                    self.assertTrue(b['opening_recovered'])
                    self.assertTrue(b['translation'].endswith(' '+a['translation']))

    def test_tail_diagnostic_cannot_improve_an_unchanged_fixed_control(self):
        report=latest_windows_diagnostics()['windows8030_tail_translation_replay']
        fixed=report['cohorts']['all124_fixed_reading_viewports'];d=report['tail_diagnostic']
        self.assertEqual((fixed['before_not_approved'],fixed['after_not_approved'],fixed['corrected'],fixed['regressed']),(56,56,0,0))
        self.assertEqual((d['accepted_changed_regions'],d['complete_corrections'],d['partial_improvements_with_residual_errors'],d['rejected_additions']),(10,6,4,1))
        self.assertTrue(d['counts_not_added_to_fixed_views_or_previous_diagnostics'])
        self.assertEqual(report['fixed_complete_location_judgments_reused_by_identity'],124)
        self.assertFalse(report['fresh_native_ocr'])
        self.assertTrue(report['fresh_translation_inference'])
        self.assertFalse(report['all_chapter_words_visually_reviewed'])
        self.assertIsNone(report['screen_attempt_failure_probability'])
        self.assertFalse(report['target_achieved'])

    def test_integrated_tail_inputs_never_include_reference_or_expected_answers(self):
        from audit_corpus_quality import QA,records,read
        folder=QA/'windows8030-tail-translation-replay'
        inputs=[r for n in range(6) for r in records(folder/f'part-{n:02d}.input.jsonl')]
        self.assertEqual(len(inputs),334)
        self.assertTrue(all(set(r)=={'id','source','image','bounds'} for r in inputs))
        changes=read(folder/'changes.json')
        self.assertNotIn(82,[r['id'] for r in changes])
        self.assertTrue(all(r['actual_native']['translation'].startswith(r['policy']['translation']) for r in changes))

    def test_tail_full_reports_keep_every_region_and_existing_translation_prefix(self):
        from audit_corpus_quality import QA,read,records,digest
        import os
        paths=list((QA/'postprocessed-en8030-tails').glob('*.done.json'));self.assertGreater(len(paths),0)
        for path in paths:
            value=read(path);base=QA/'postprocessed-en8029-refinement'/path.name
            raw=base.with_name(base.name.replace('.done.json','.jsonl'));target=path.with_name(path.name.replace('.done.json','.jsonl'))
            self.assertEqual(value['tail_derivation_proof']['parent_report_sha256'],digest(raw))
            self.assertFalse(value['new_ocr_inference']);self.assertFalse(value['word_review_complete'])
            self.assertFalse(value['fresh_translation_for_all_regions'])
            before,after=records(raw),records(target);self.assertEqual(len(before),len(after))
            changed=0
            for a,b in zip(before,after):
                self.assertEqual((a['image'],a['bounds'],a['source']),(b['image'],b['bounds'],b['source']))
                if a['translation']!=b['translation']:
                    changed+=1;self.assertTrue(b['tail_recovered'])
                    self.assertTrue(b['translation'].startswith(a['translation']))
            self.assertEqual(changed,value['tail_translation_regions_changed'])
            if value['shared_immutable_core_report']:self.assertTrue(os.path.samefile(raw,target))

    def test_derived_corpus_does_not_masquerade_as_fresh_ocr_or_drop_regions(self):
        from audit_corpus_quality import QA,read,records,digest
        import os
        paths=list((QA/'postprocessed-en8027-questions').glob('*.done.json'))
        self.assertGreater(len(paths),0)
        for path in paths:
            value=read(path);original=QA/'translated-en8026-inflection'/path.name
            base=read(original);raw=original.with_name(original.name.replace('.done.json','.jsonl'))
            derived=path.with_name(path.name.replace('.done.json','.jsonl'))
            self.assertEqual(value['engine'],base['engine'])
            self.assertEqual(value['display_build'],'802701')
            self.assertEqual(value['image_signature'],base['image_signature'])
            self.assertEqual(value['regions'],base['regions'])
            self.assertFalse(value['fresh_capture_in_display_build'])
            self.assertFalse(value['new_ocr_inference'])
            self.assertFalse(value['new_decoder_inference'])
            self.assertFalse(value['word_review_complete'])
            self.assertEqual(value['derivation_proof']['native_report_sha256'],digest(raw))
            before,after=records(raw),records(derived)
            self.assertEqual(len(before),len(after))
            for a,b in zip(before,after):
                self.assertEqual((a['image'],a['bounds'],a['source']),(b['image'],b['bounds'],b['source']))
            if value['shared_immutable_core_report']:
                self.assertTrue(os.path.samefile(raw,derived))
                self.assertEqual(digest(raw),digest(derived))

if __name__ == '__main__':
    unittest.main()
