CHB-COP on window 0, one core of the Xeon Silver 4216 (several such processes in parallel). Algorithm 1: time per unit (median, max). Per scope: parts, dependent pairs after the independence test, pair-copula selection, and synthesis (exact integration for two parts, Monte-Carlo with N draws for the tail plus 1e+06 for the body otherwise). Seconds.

| program | units | Alg. 1 median, max | scope | parts | dependent pairs | selection | synthesis | synthesis s | total |
|---|---|---|---|---|---|---|---|---|---|
| bsort100 | 2 | 10.3, 10.3 | BubbleSort | 2 | 0 | 0.1 | exact | 0.4 | 21 |
| cb1 | 24 | 12.8, 15.7 | EKFLocalizer::update_diagnostics | 4 | 3 | 13.2 | MC N=1e+07 | 502.3 | 3976 |
|  | |  | EKFLocalizer::update_predict_frequency.if1.then | 2 | 1 | 4.3 | exact | 63.0 | |
|  | |  | EKFLocalizer::update_predict_frequency | 2 | 1 | 4.5 | exact | 62.5 | |
|  | |  | EKFLocalizer::timer_callback.if3.then.L1 | 2 | 1 | 4.0 | exact | 7.5 | |
|  | |  | EKFLocalizer::timer_callback.if3.then | 2 | 1 | 4.9 | exact | 38.5 | |
|  | |  | EKFLocalizer::timer_callback.if4.then.L1 | 2 | 1 | 5.2 | exact | 6.1 | |
|  | |  | EKFLocalizer::timer_callback.if4.then | 2 | 1 | 4.3 | exact | 6.8 | |
|  | |  | EKFLocalizer::timer_callback | 12 | 38 | 169.7 | MC N=1e+07 | 2773.3 | |
| cb2 | 3 | 11.5, 12.2 | Twist2Accel::callback_odometry | 3 | 1 | 5.5 | MC N=1e+07 | 1.8 | 41 |
| cb3 | 1 | 12.0, 12.0 | – | 1 | – | – | – | – | 12 |
| cb4 | 74 | 10.8, 15.7 | Controller::check_cyclic_message_timeout | 3 | 1 | 3.5 | MC N=1e+07 | 203.7 | 12358 |
|  | |  | Controller::createInputData | 3 | 1 | 4.8 | MC N=1e+07 | 173.0 | |
|  | |  | Controller::isTimeOut | 3 | 0 | 0.0 | MC N=1e+07 | 1.9 | |
|  | |  | MpcLateralController::isReady | 5 | 1 | 4.4 | MC N=1e+07 | 5.5 | |
|  | |  | MPC::applyVelocityDynamicsFilter | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | MPC::calcDesiredSteeringRate | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | MPC::calcSteerRateLimitOnTrajectory.L1 | 2 | 1 | 5.1 | exact | 7.4 | |
|  | |  | MPC::calcSteerRateLimitOnTrajectory | 3 | 1 | 4.9 | MC N=1e+07 | 163.5 | |
|  | |  | MPC::executeOptimization | 5 | 1 | 4.9 | MC N=1e+07 | 134.6 | |
|  | |  | MPC::generateMPCMatrix.L1 | 2 | 1 | 5.0 | exact | 8.6 | |
|  | |  | MPC::generateMPCMatrix | 3 | 3 | 13.6 | MC N=1e+07 | 122.5 | |
|  | |  | MPC::getData | 3 | 0 | 0.0 | MC N=1e+07 | 2.0 | |
|  | |  | MPC::resampleMPCTrajectoryByTime | 4 | 2 | 8.4 | MC N=1e+07 | 16.6 | |
|  | |  | MPC::updateStateForDelayCompensation.L1 | 2 | 1 | 4.8 | exact | 6.1 | |
|  | |  | MPC::updateStateForDelayCompensation | 2 | 1 | 3.6 | exact | 10.3 | |
|  | |  | MPC::calculateMPC | 17 | 62 | 281.5 | MC N=1e+07 | 6100.3 | |
|  | |  | MpcLateralController::createCtrlCmdHorizonMsg | 2 | 1 | 5.3 | exact | 4.7 | |
|  | |  | MpcLateralController::isTrajectoryShapeChanged | 2 | 1 | 3.7 | exact | 8.2 | |
|  | |  | MpcLateralController::isSteerConverged | 3 | 2 | 8.3 | MC N=1e+07 | 7.0 | |
|  | |  | MpcLateralController::run | 10 | 20 | 97.4 | MC N=1e+07 | 1260.7 | |
|  | |  | PidLongitudinalController::checkControlState | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | Controller::callbackTimerControl | 15 | 37 | 170.4 | MC N=1e+07 | 2677.1 | |
| cb5 | 8 | 12.3, 13.7 | ScanGroundFilterComponent::extractObjectPoints | 2 | 0 | 0.0 | exact | 0.5 | 1077 |
|  | |  | ScanGroundFilterComponent::faster_filter | 7 | 9 | 43.3 | MC N=1e+07 | 937.6 | |
| cb6 | 31 | 9.9, 12.9 | LaneDepartureCheckerNode::onTimer.L1 | 2 | 1 | 5.2 | exact | 7.8 | 1963 |
|  | |  | LaneDepartureCheckerNode::checkLaneDeparture | 4 | 0 | 0.1 | MC N=1e+07 | 2.9 | |
|  | |  | LaneDepartureCheckerNode::createMarkerArray.if2.then | 3 | 3 | 15.1 | MC N=1e+07 | 221.8 | |
|  | |  | LaneDepartureCheckerNode::createMarkerArray | 6 | 4 | 17.8 | MC N=1e+07 | 466.6 | |
|  | |  | LaneDepartureCheckerNode::isDataReady | 8 | 0 | 0.3 | MC N=1e+07 | 10.8 | |
|  | |  | LaneDepartureCheckerNode::isDataTimeout | 2 | 0 | 0.0 | exact | 0.6 | |
|  | |  | LaneDepartureCheckerNode::onTimer | 11 | 12 | 57.8 | MC N=1e+07 | 833.2 | |
| cb7 | 18 | 12.1, 12.8 | NDTScanMatcher::publish_marker.L1 | 2 | 1 | 3.7 | exact | 6.3 | 1772 |
|  | |  | NDTScanMatcher::publish_marker | 3 | 3 | 13.5 | MC N=1e+07 | 126.5 | |
|  | |  | NDTScanMatcher::publish_pose | 2 | 1 | 4.8 | exact | 7.5 | |
|  | |  | NDTScanMatcher::transform_sensor_measurement | 2 | 1 | 5.0 | exact | 19.2 | |
|  | |  | NDTScanMatcher::callback_sensor_points_main | 11 | 21 | 91.8 | MC N=1e+07 | 1275.1 | |
|  | |  | NDTScanMatcher::callback_sensor_points | 3 | 1 | 3.0 | MC N=1e+07 | 6.5 | |
| cnt | 2 | 10.0, 10.1 | Sum | 2 | 1 | 5.1 | exact | 3.0 | 28 |
| edn | 4 | 10.1, 10.5 | fir | 2 | 1 | 5.7 | exact | 7.2 | 111 |
|  | |  | main | 3 | 1 | 6.0 | MC N=1e+08 | 51.6 | |
| fir | 2 | 10.2, 10.4 | fir_filter_int | 2 | 0 | 0.1 | exact | 0.4 | 21 |
| lms | 3 | 10.0, 10.3 | main | 3 | 2 | 9.1 | MC N=1e+08 | 1492.6 | 1532 |
| ludcmp | 5 | 10.1, 10.3 | ludcmp | 5 | 5 | 21.3 | MC N=1e+08 | 3407.5 | 3480 |
| matmult | 2 | 10.1, 10.2 | Multiply | 2 | 1 | 4.0 | exact | 3.4 | 28 |
| ndes | 4 | 14.3, 14.6 | des | 4 | 1 | 5.7 | MC N=1e+08 | 794.8 | 858 |
| prime | 1 | 14.9, 14.9 | – | 1 | – | – | – | – | 15 |
| qsort-exam | 2 | 10.3, 10.4 | sort | 2 | 0 | 0.1 | exact | 0.4 | 21 |
| select | 2 | 10.6, 10.7 | select | 2 | 1 | 4.7 | exact | 2.1 | 28 |
| st | 6 | 13.9, 14.6 | Calc_LinCorrCoef | 2 | 1 | 5.1 | exact | 8.0 | 7112 |
|  | |  | main | 5 | 10 | 40.1 | MC N=1e+08 | 6977.1 | |
