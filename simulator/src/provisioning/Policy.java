package provisioning;

/** How the broker estimates the demand it must serve in the interval after next. */
public enum Policy {
    /** Fixed VM count sized from the hindsight peak of the day. */
    STATIC_PEAK,
    /** Target tracking on the latest measurement, the usual cloud autoscaler. */
    REACTIVE,
    /** Uses the machine learning forecast. */
    PROACTIVE,
    /** Forecast plus a safety margin taken from validation errors. */
    PROACTIVE_MARGIN,
    /** Uses the true future demand; an upper bound for any forecast. */
    ORACLE
}
