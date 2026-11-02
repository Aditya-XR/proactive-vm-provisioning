package provisioning;

import java.util.Arrays;

/**
 * Hand-computable scenarios that confirm the simulator behaves as designed.
 * Exits non-zero if any check fails.
 */
public final class SimulatorChecks {
    private static int failures;

    private SimulatorChecks() {
    }

    private static Scenario constant(double[] demand) {
        double[] forecast = demand.clone();
        forecast[0] = Double.NaN;
        return new Scenario("check", demand, forecast, 1, demand.length - 2);
    }

    private static double[] fill(int size, double value) {
        double[] out = new double[size];
        Arrays.fill(out, value);
        return out;
    }

    private static void expect(String name, double actual, double expected, double tolerance) {
        boolean ok = Math.abs(actual - expected) <= tolerance;
        System.out.printf("%-58s expected %10.3f  measured %10.3f  %s%n", name, expected, actual, ok ? "PASS" : "FAIL");
        if (!ok) {
            failures++;
        }
    }

    public static void main(String[] args) throws Exception {
        Settings at80 = new Settings().withTarget(0.8);

        // Steady 1600 MIPS at target 0.8 needs 2 VMs of 1000 MIPS, so each runs at 80 percent.
        RunResult steady = Simulation.run(constant(fill(20, 1600)), Policy.REACTIVE, at80, 0);
        expect("steady load: VMs in use", steady.peakVms(), 2, 0);
        expect("steady load: response = 60 s x 0.8", steady.meanResponse(), 48, 0.2);
        expect("steady load: SLA violations (percent)", steady.slaViolationPercent(), 0, 0);
        expect("steady load: all submitted work completes", steady.completedMi, steady.submittedMi, 0);

        // One VM at 1200 MIPS for a static pool: backlog grows 200 MI per second.
        double[] overload = fill(20, 800);
        for (int t = 5; t < 8; t++) {
            overload[t] = 3200;
        }
        RunResult reactive = Simulation.run(constant(overload), Policy.REACTIVE, at80, 0);
        RunResult oracle = Simulation.run(constant(overload), Policy.ORACLE, at80, 0);
        expect("step: reactive VMs before the step (interval 5)", reactive.readyVmsAt(5), 1, 0);
        expect("step: reactive sees it at tick 6, VMs ready at 7", reactive.readyVmsAt(7), 4, 0);
        expect("step: oracle has VMs ready when it starts", oracle.readyVmsAt(5), 4, 0);
        expect("step: oracle meets the SLA throughout (percent)", oracle.slaViolationPercent(), 0, 0);
        System.out.printf("step: reactive late slices %.2f%%, max response %.1f s (must be above the SLA)%n",
                reactive.slaViolationPercent(), reactive.percentile(1.0));
        if (reactive.slaViolationPercent() == 0) {
            failures++;
        }

        // Billing: 3 VMs for the whole run under a static pool, ending with the last cloudlet.
        RunResult fixed = Simulation.run(constant(fill(10, 2400)), Policy.STATIC_PEAK, at80, 0);
        expect("static: VM count from the peak", fixed.peakVms(), 3, 0);
        double seconds = 8 * 300;
        expect("static: billed VM hours for 3 VMs over 8 intervals", fixed.billedVmSeconds / 3600, 3 * seconds / 3600, 0.02);
        expect("static: utilization equals the target", 100 * fixed.completedMi / (fixed.readyVmSeconds * 1000), 80, 1.5);

        System.out.println(failures == 0 ? "ALL CHECKS PASSED" : failures + " CHECK(S) FAILED");
        System.exit(failures == 0 ? 0 : 1);
    }
}
