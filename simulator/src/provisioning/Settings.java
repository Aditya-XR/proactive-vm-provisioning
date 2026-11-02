package provisioning;

/** Simulation assumptions; report section 3.5 justifies each value. */
public final class Settings {
    public double targetUtilization = 0.8;
    public final double vmMips = 1000;
    public final int vmRamMb = 2048;
    public final long vmBwMbps = 1000;
    public final long vmImageMb = 10_000;
    public final int minVms = 1;
    public final int maxVms = 64;
    public final double bootDelaySeconds = 240;
    public final int scaleInTicks = 3;
    public final double sliceSeconds = 60;
    public final int slicesPerInterval = 5;
    /** A slice is late if it takes longer than this; one second allows for event rounding. */
    public final double slaSeconds = 61;

    public final int hosts = 5;
    public final int hostCores = 16;
    public final int hostRamMb = 32_768;
    public final long hostBwMbps = 10_000;
    public final long hostStorageMb = 1_000_000;

    public Settings withTarget(double value) {
        Settings copy = new Settings();
        copy.targetUtilization = value;
        return copy;
    }
}
