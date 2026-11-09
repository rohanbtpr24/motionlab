# Bike-fit evidence and validation plan

Status: engineering and research plan. This document does not implement a recommendation engine, and the current application does not have professional bike-fitter accuracy. A complete understanding of every rider and every fit problem cannot be guaranteed by a model or a knowledge library. The product should make bounded, explainable claims whose measurements and evidence can be checked.

## Immediate experiment: baseline versus seatpost +20 mm

Retain both original side recordings with distinct generated video IDs. Label the original position Baseline and the new position Seatpost +20 mm. Record this as a self-reported **seatpost extension change**, not a measured vertical saddle-height change or a 20 mm measurement inferred from pixels. The extension annotation is relative to the rider's stated baseline; it is not an absolute geometry measurement or a machine-verified relationship to every possible comparison selection.

Select steady pedaling from each recording with similar camera placement, cadence, workload, footwear, hand position, and riding posture. Use the same visible anatomical side. These are separate sessions. A clap does not align different pedaling events, and the application must not fuse their front/side landmarks.

The implemented comparison reports the median, 5th/95th percentiles, sample extrema, and valid-sample coverage for each joint. It subtracts baseline from candidate descriptively. These are clip distributions, not crank-phase measurements or per-cycle maxima. No zero filling, missing-value interpolation, improved/worsened classification, optimal saddle height, or causal conclusion is generated. An observed difference could be smaller than the measurement error; repeatability is not yet quantified. No performance, comfort, injury, or aerodynamic improvement can be inferred from these angle differences alone.

## Evidence informing the design

- [Millour et al., comparison of static and dynamic methods (2020)](https://pubmed.ncbi.nlm.nih.gov/32022807/): in 26 cyclists, the measurement condition changed measured knee angles; bottom-dead-centre and maximum-extension observations were also different. Product implication: store dynamic/static protocol, crank phase, angle convention, and viewing plane. Do not apply a target published for one protocol to another. This implication is an engineering interpretation, not a validated rule for MotionLab.
- [Bini and Priego-Quesada, saddle-height systematic review (2022)](https://pubmed.ncbi.nlm.nih.gov/34706617/): the review supports dynamic knee-angle assessment and describes limitations of evidence for performance/injury effects. Product implication: measure motion, separate kinematic change from outcome claims, and retain evidence quality and uncertainty.
- [Validity and reliability of different kinematics methods used for bike fitting (2014)](https://pubmed.ncbi.nlm.nih.gov/24499342/): compares dynamic methods and static measurements in cycling. This is a candidate reference for designing the validation protocol, not proof of validity for our MediaPipe implementation.

This is a small starting bibliography, not a comprehensive literature review. Abstract-level screening is insufficient to turn a paper into a production rule. Full methods, definitions, populations, results, limitations, and rights to use supporting materials must be reviewed first. No universal numerical fit targets have been added to the product.

## Measurement foundation before recommendations

1. Define each measurement precisely: anatomical reference points, 2D/3D coordinate system, angle convention, view, units, dynamic/static method, sample rate, filtering, and crank phase. The current knee output is an interior angle with 180 degrees straight; it must not silently become a published knee-flexion value. Angle-convention conversion alone does not make protocols interchangeable.
2. Validate manual physical-marker labeling and automatic marker association against annotated video. Repeated colors, occlusion, reflections, clothing, skin tones, HDR, and left/right identity require explicit evaluation. Current MediaPipe landmarks are not automatically the physical colored dots.
3. Build a consented evaluation set with manual reference annotations and repeated trials. Compare against an appropriate reference system and qualified fitter annotations; record inter-rater and intra-rater disagreement rather than treating a single annotation as exact ground truth.
4. Measure angular error, bias, limits of agreement, tracking dropout, side swaps, and within-session/between-session repeatability by joint and recording condition. Define acceptance thresholds before evaluating held-out data. Report coverage separately from accuracy. A high model confidence score is not an angular error estimate.
5. Add reliable crank/pedal reference tracking and cycle segmentation before comparing angle-at-phase or aggregating per-cycle extrema. Exclude non-pedaling periods and evaluate sensitivity to sample rate and dropped frames.
6. Determine when a change is distinguishable from measurement noise, using the validated repeatability results. Do not invent an uncertainty band or assume that a two-degree difference is meaningful.

## Versioned evidence and recommendation layer

Keep domain knowledge separate from landmark detection and geometric calculations. A future evidence item should include a stable ID, source DOI/URL, publication and review dates, claim, population, cycling discipline, outcome, study design/quality, measurement protocol, angle convention, applicable conditions, limitations, reviewer, and version. Evidence strength and applicability must remain visible to the decision layer.

A future recommendation should reference the measurement version, supporting evidence IDs, relevant rider/bike context, applicable conditions, rationale, uncertainty, suggested bounded experiment, and reassessment criteria. Unsupported or mismatched inputs should yield insufficient evidence, not a fabricated answer. Conflicting sources should remain represented rather than being flattened into a single universal range.

Candidate knowledge domains include saddle height/fore-aft/tilt; crank length; cleat/foot position; reach/drop; upper-body position; rider goals and discipline; mobility and individual anatomy; workload/cadence; comfort and symptoms; adaptation over time. Their inclusion here is a roadmap, not an implemented assessment.

## Release gates

- Current: local ingestion, model-based 2D tracking, confidence gating, descriptive independent-session comparisons. No recommendation release.
- Next: physically labeled marker tracking, annotated evaluation, repeatability estimates, crank-phase measurements, and explicit recording-quality checks.
- Then: expert-reviewed evidence registry and testable recommendation candidates, evaluated on held-out cases with qualified fitters. Claims must be limited to the populations and protocols actually validated.
- Later: prospective outcome evaluation, follow-up feedback, calibration/3D validation where justified, and monitored versioned releases. Pain, injury diagnosis, and rehabilitation decisions are separate from a kinematic bike-fit tool.
