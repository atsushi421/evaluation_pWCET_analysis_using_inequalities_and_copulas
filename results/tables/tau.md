# Dependence between units: Kendall's tau

Kendall's tau of the pairs that the CHB-COP composition couples directly, i.e. the first-tree edges of every R-vine node and every two-part node, as stored in the CHB-COP meta of the estimate JSONs (pairs of deeper trees are conditional and left out). Independence rejected: share of these pairs whose Kendall-tau independence pre-test rejected at 0.05. Sources: results/estimates/*.json (all windows with CHB-COP: 0-49, or 0-9 for the R-vine kernels), results/estimates_autoware_warm1/*.json (window 0).

## Benchmarks

| kernel | windows | pairs per window | median abs tau | max abs tau (window) | max abs tau w0 | strongest pair (sign) | its tau over windows | independence rejected |
|---|---|---|---|---|---|---|---|---|
| bsort100 | 50 | 1 | 0.006 | 0.098 (w16) | 0.004 | BubbleSort: BubbleSort.L1 / BubbleSort.self (+) | -0.02 to +0.10 | 16 % |
| fir | 50 | 1 | 0.117 | 0.161 (w29) | 0.003 | fir_filter_int: fir_filter_int.L1 / fir_filter_int.self (+) | -0.00 to +0.16 | 98 % |
| matmult | 50 | 1 | 0.043 | 0.063 (w12) | 0.060 | Multiply: Multiply.L1 / Multiply.self (+) | +0.03 to +0.06 | 100 % |
| edn | 10 | 3 | 0.021 | 0.861 (w1) | 0.397 | fir: fir.L1 / fir.self (-) | -0.86 to -0.40 | 60 % |
| ndes | 10 | 3 | 0.020 | 0.059 (w8) | 0.022 | des: des.L2 / max(des.if2) (-) | -0.06 to -0.02 | 73 % |
| st | 10 | 5 | 0.219 | 0.472 (w2) | 0.470 | Calc_LinCorrCoef: Calc_LinCorrCoef.L1 / Calc_LinCorrCoef.self (-) | -0.47 to -0.28 | 100 % |
| lms | 10 | 2 | 0.049 | 0.074 (w4) | 0.035 | main: main.L2 / main.self (-) | -0.07 to -0.01 | 100 % |
| prime | 50 | 0 | - | - | - | - | - | single unit, no composition |
| cnt | 50 | 1 | 0.010 | 0.032 (w12) | 0.015 | Sum: Sum.L1 / Sum.self (+) | -0.01 to +0.03 | 30 % |
| ludcmp | 10 | 4 | 0.035 | 0.175 (w8) | 0.160 | ludcmp: ludcmp.L3 / ludcmp.self (-) | -0.18 to +0.08 | 82 % |
| select | 50 | 1 | 0.045 | 0.062 (w21) | 0.045 | select: select.L1 / select.self (+) | +0.03 to +0.06 | 100 % |
| qsort-exam | 50 | 1 | 0.005 | 0.020 (w29) | 0.010 | sort: sort.L1 / sort.self (+) | -0.02 to +0.02 | 14 % |

Pairs whose abs tau reaches 0.1 in some window (signed range over the windows where the pair is coupled directly):

| kernel | pair | windows | min tau | max tau |
|---|---|---|---|---|
| fir | fir_filter_int: fir_filter_int.L1 / fir_filter_int.self | 50 | -0.003 | +0.161 |
| edn | fir: fir.L1 / fir.self | 10 | -0.861 | -0.397 |
| st | Calc_LinCorrCoef: Calc_LinCorrCoef.L1 / Calc_LinCorrCoef.self | 10 | -0.472 | -0.279 |
| st | main: Calc_LinCorrCoef / Initialize (avg x2) | 10 | +0.175 | +0.267 |
| st | main: Calc_Sum_Mean (avg x2) / main.self | 10 | -0.255 | -0.212 |
| st | main: Calc_Var_Stddev (avg x2) / main.self | 10 | -0.184 | -0.118 |
| ludcmp | ludcmp: ludcmp.L3 / ludcmp.self | 10 | -0.175 | +0.081 |
| ludcmp | ludcmp: ludcmp.L1 / ludcmp.L3 | 2 | -0.160 | +0.021 |

## Autoware, window 0

| callback | pairs | median abs tau | tau of the strongest pair | strongest pair |
|---|---|---|---|---|
| cb1 | 18 | 0.162 | +0.342 | EKFLocalizer::timer_callback: EKFModule::get_current_pose (avg x2) / max(EKFLocalizer::timer_callback.if4) |
| cb2 | 2 | 0.013 | -0.015 | Twist2Accel::callback_odometry: AccelEstimator::estimate#3 / Twist2Accel::callback_odometry.self |
| cb3 | 0 | - | - | single unit, no composition |
| cb4 | 70 | 0.075 | +0.903 | MpcLateralController::isTrajectoryShapeChanged: MpcLateralController::isTrajectoryShapeChanged.L1 / MpcLateralController::isTrajectoryShapeChanged.self |
| cb5 | 7 | 0.026 | +0.647 | ScanGroundFilterComponent::faster_filter: ScanGroundFilterComponent::extractObjectPoints / ScanGroundFilterComponent::faster_filter.self |
| cb6 | 28 | 0.012 | +0.646 | LaneDepartureCheckerNode::onTimer: LaneDepartureCheckerNode::createMarkerArray / LaneDepartureCheckerNode::onTimer.self |
| cb7 | 16 | 0.079 | +0.377 | NDTScanMatcher::callback_sensor_points_main: NDTScanMatcher::publish_pose / NDTScanMatcher::publish_tf |
