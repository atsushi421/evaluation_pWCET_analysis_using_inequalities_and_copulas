CHB-COP on window 0, one core of the Xeon Silver 4216 (several such processes in parallel). Algorithm 1: time per unit (median, max). Per scope: parts, dependent pairs after the independence test, pair-copula selection, and synthesis (exact integration for two parts, Monte-Carlo with N draws for the tail plus 1e+06 for the body otherwise). Seconds.

| program | units | Alg. 1 median, max | scope | parts | dependent pairs | selection | synthesis | synthesis s | total |
|---|---|---|---|---|---|---|---|---|---|
| bsort100 | 2 | 10.3, 10.3 | BubbleSort | 2 | 0 | 0.1 | exact | 0.4 | 21 |
| cb1 | 22 | 13.2, 14.5 | EKFLocalizer::update_diagnostics | 4 | 3 | 12.7 | MC N=1e+07 | 484.1 | 3899 |
|  | |  | EKFLocalizer::update_predict_frequency.if1.then | 2 | 1 | 4.2 | exact | 63.3 | |
|  | |  | EKFLocalizer::update_predict_frequency | 2 | 1 | 4.5 | exact | 62.8 | |
|  | |  | EKFLocalizer::timer_callback.if3.then | 2 | 1 | 3.2 | exact | 31.3 | |
|  | |  | EKFLocalizer::timer_callback.if4.then | 2 | 1 | 3.9 | exact | 7.2 | |
|  | |  | EKFLocalizer::timer_callback | 12 | 38 | 168.8 | MC N=1e+07 | 2774.4 | |
| cb2 | 3 | 11.5, 12.2 | Twist2Accel::callback_odometry | 3 | 1 | 5.5 | MC N=1e+07 | 1.8 | 41 |
| cb3 | 1 | 12.0, 12.0 | – | 1 | – | – | – | – | 12 |
| cb4 | 71 | 11.0, 14.6 | Controller::check_cyclic_message_timeout | 3 | 1 | 3.4 | MC N=1e+07 | 196.8 | 12222 |
|  | |  | Controller::createInputData | 3 | 1 | 4.1 | MC N=1e+07 | 162.6 | |
|  | |  | Controller::isTimeOut | 3 | 0 | 0.0 | MC N=1e+07 | 1.9 | |
|  | |  | MpcLateralController::isReady | 5 | 1 | 4.4 | MC N=1e+07 | 5.5 | |
|  | |  | MPC::applyVelocityDynamicsFilter | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | MPC::calcDesiredSteeringRate | 2 | 0 | 0.0 | exact | 0.6 | |
|  | |  | MPC::calcSteerRateLimitOnTrajectory | 3 | 1 | 4.9 | MC N=1e+07 | 163.1 | |
|  | |  | MPC::executeOptimization | 5 | 1 | 4.9 | MC N=1e+07 | 134.0 | |
|  | |  | MPC::generateMPCMatrix | 3 | 3 | 13.7 | MC N=1e+07 | 121.9 | |
|  | |  | MPC::getData | 3 | 0 | 0.0 | MC N=1e+07 | 2.0 | |
|  | |  | MPC::resampleMPCTrajectoryByTime | 4 | 2 | 8.3 | MC N=1e+07 | 16.6 | |
|  | |  | MPC::updateStateForDelayCompensation | 2 | 1 | 3.6 | exact | 10.1 | |
|  | |  | MPC::calculateMPC | 17 | 62 | 281.5 | MC N=1e+07 | 6076.2 | |
|  | |  | MpcLateralController::createCtrlCmdHorizonMsg | 2 | 1 | 5.3 | exact | 4.7 | |
|  | |  | MpcLateralController::isTrajectoryShapeChanged | 2 | 1 | 0.8 | exact | 7.6 | |
|  | |  | MpcLateralController::isSteerConverged | 3 | 0 | 0.0 | MC N=1e+07 | 1.9 | |
|  | |  | MpcLateralController::run | 10 | 20 | 96.1 | MC N=1e+07 | 1262.5 | |
|  | |  | PidLongitudinalController::checkControlState | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | Controller::callbackTimerControl | 15 | 37 | 170.1 | MC N=1e+07 | 2661.7 | |
| cb5 | 8 | 12.3, 13.7 | ScanGroundFilterComponent::extractObjectPoints | 2 | 0 | 0.0 | exact | 0.5 | 1077 |
|  | |  | ScanGroundFilterComponent::faster_filter | 7 | 9 | 43.3 | MC N=1e+07 | 937.6 | |
| cb6 | 30 | 11.3, 14.6 | LaneDepartureCheckerNode::checkLaneDeparture | 4 | 0 | 0.1 | MC N=1e+07 | 3.0 | 2120 |
|  | |  | LaneDepartureCheckerNode::createMarkerArray.if2.then | 3 | 3 | 12.1 | MC N=1e+07 | 378.2 | |
|  | |  | LaneDepartureCheckerNode::createMarkerArray | 6 | 4 | 17.7 | MC N=1e+07 | 465.7 | |
|  | |  | LaneDepartureCheckerNode::isDataReady | 8 | 0 | 0.3 | MC N=1e+07 | 10.9 | |
|  | |  | LaneDepartureCheckerNode::isDataTimeout | 2 | 0 | 0.0 | exact | 0.5 | |
|  | |  | LaneDepartureCheckerNode::onTimer | 11 | 12 | 58.0 | MC N=1e+07 | 832.2 | |
| cb7 | 17 | 12.2, 13.0 | NDTScanMatcher::publish_marker | 3 | 3 | 13.5 | MC N=1e+07 | 126.3 | 1755 |
|  | |  | NDTScanMatcher::publish_pose | 2 | 1 | 4.8 | exact | 7.5 | |
|  | |  | NDTScanMatcher::transform_sensor_measurement | 2 | 1 | 5.0 | exact | 19.1 | |
|  | |  | NDTScanMatcher::callback_sensor_points_main | 11 | 21 | 91.6 | MC N=1e+07 | 1278.8 | |
|  | |  | NDTScanMatcher::callback_sensor_points | 3 | 1 | 2.9 | MC N=1e+07 | 6.4 | |
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
