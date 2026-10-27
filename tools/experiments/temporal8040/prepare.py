"""Freeze a general temporal veto before any control likelihoods are computed."""
import importlib.metadata
from pathlib import Path

from tools.experiments.stability8035.core import ROOT, read, sha, write_new
from .route import META


def main():
    install = read(ROOT / 'build/grammar8040-install.json')
    model = next(row for row in install['install'] if row['metadata']['name'].replace('_', '-') == 'es-core-news-sm')
    import es_core_news_sm
    directory = Path(es_core_news_sm.__file__).parent
    write_new(META / 'grammar-provenance.json', dict(
        model='es_core_news_sm', version='3.8.0', spacy_version=importlib.metadata.version('spacy'),
        license='GNU GPL 3.0', research_only_not_in_application=True,
        official_metadata='https://raw.githubusercontent.com/explosion/spacy-models/master/meta/es_core_news_sm-3.8.0.json',
        wheel=model['download_info'],
        files=[dict(path=str(path.relative_to(ROOT)), sha256=sha(path)) for path in sorted(directory.rglob('*'))
               if path.is_file() and '__pycache__' not in str(path)]))
    paths = [
        'benchmarks/roundtrip8039/result.json', 'benchmarks/roundtrip8039/model-provenance.json',
        'benchmarks/qe8038/native-validation-meaning-decisions.json',
        'benchmarks/qe8038/native-control-meaning-decisions.json', 'build/qe8038/candidate-pools.json',
        'build/roundtrip8039/validation-inverse-scores.json',
        'tools/experiments/roundtrip8039/score.py', 'tools/train_opus_lora8031.py',
        'benchmarks/temporal8040/grammar-provenance.json',
    ]
    paths += [str(path.relative_to(ROOT)) for path in Path(__file__).parent.glob('*.py')]
    write_new(META / 'protocol.json', dict(
        schema=1, experiment='8040-inverse-likelihood-with-temporal-retention',
        immutable_inputs=[dict(path=path, sha256=sha(ROOT / path)) for path in paths],
        development_history='Designed after the 8039 validation temporal uncertainty; not an independent test and does not change the failed 8039 gates.',
        candidate_pool=['native803001', 'base_float', 'adapter8034_full'],
        policy='Default native. Accept only format-valid, strictly higher inverse-likelihood candidates whose coarse Spanish temporal categories contain every native category. Highest likelihood wins; pool order breaks ties. No margin tuning, source-word rules, reference inputs or sentence rewriting.',
        temporal_categories=['past', 'present', 'future', 'conditional'],
        temporal_scope='Finite verb and auxiliary morphology. Present haber with participle maps to past; future/conditional perfect keeps auxiliary time. No claim of clause alignment or complete temporal semantics.',
        score='Reuse fixed 8039 reverse OPUS mean log probability of original English conditioned on candidate Spanish. English original is the reverse target, no Spanish reference is used. No gradients.',
        validation_gates=dict(minimum_complete_corrections=1, maximum_new_content_regressions=0,
                              maximum_additional_partial_losses=0, maximum_new_source_artifacts=0,
                              maximum_new_context_uncertainties=0),
        controls_gates=dict(minimum_net_complete_corrections=1, maximum_new_content_regressions=0,
                            maximum_additional_partial_losses=0, maximum_new_source_artifacts=0,
                            maximum_new_context_uncertainties=0),
        single_preregistered_policy=True, freeze_selection_before_control_scoring=True,
        grammar_license='GPL-3.0; isolated research dependency, not bundled in app',
        new_blind_test_chapters_opened=0, production_weights_modified=False,
        app_failure_probability=None, target_achieved=False))


if __name__ == '__main__':
    main()
