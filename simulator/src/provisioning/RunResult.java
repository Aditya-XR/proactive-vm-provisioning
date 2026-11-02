package provisioning;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

/** Everything measured in one simulation run. */
public final class RunResult {
    public static final String SUMMARY_HEADER = "scenario,policy,target_utilization,billed_vm_hours,ready_vm_hours,"
            + "pool_utilization_pct,sla_violation_pct,mean_response_s,p95_response_s,p99_response_s,max_response_s,"
            + "overloaded_intervals,intervals,scale_ups,scale_downs,peak_vms,failed_vm_creations,submitted_mi,completed_mi,"
            + "peak_memory_gb,mean_memory_gb";
    public static final String INTERVAL_HEADER = "scenario,policy,target_utilization,interval,demand_mips,planned_mips,"
            + "target_vms,ready_vms,booting_vms,capacity_mips,offered_utilization_pct,memory_gb,mean_response_s,late_slices";

    private static final class Row {
        int interval;
        double demand;
        double planned;
        int target;
        int ready;
        int booting;
        double capacity;
    }

    private final Scenario scenario;
    private final Policy policy;
    private final Settings settings;
    private final List<Row> rows = new ArrayList<>();
    private final Map<Integer, double[]> responseByInterval = new HashMap<>();
    private double[] sortedResponses = new double[0];

    public double billedVmSeconds;
    public double readyVmSeconds;
    public double submittedMi;
    public double completedMi;
    public int scaleUps;
    public int scaleDowns;
    public int failedVmCreations;

    RunResult(Scenario scenario, Policy policy, Settings settings) {
        this.scenario = scenario;
        this.policy = policy;
        this.settings = settings;
    }

    void addInterval(int interval, double demand, double planned, int target, int ready, int booting, double capacity) {
        Row row = new Row();
        row.interval = interval;
        row.demand = demand;
        row.planned = planned;
        row.target = target;
        row.ready = ready;
        row.booting = booting;
        row.capacity = capacity;
        rows.add(row);
    }

    void addResponse(int interval, double seconds) {
        double[] slot = responseByInterval.computeIfAbsent(interval, k -> new double[3]);
        slot[0] += seconds;
        slot[1] += 1;
        if (seconds > settings.slaSeconds) {
            slot[2] += 1;
        }
    }

    void setResponses(double[] sorted) {
        sortedResponses = sorted;
    }

    public double percentile(double q) {
        if (sortedResponses.length == 0) {
            return 0;
        }
        int index = (int) Math.ceil(q * sortedResponses.length) - 1;
        return sortedResponses[Math.max(0, index)];
    }

    public double meanResponse() {
        double sum = 0;
        for (double value : sortedResponses) {
            sum += value;
        }
        return sortedResponses.length == 0 ? 0 : sum / sortedResponses.length;
    }

    public double slaViolationPercent() {
        int late = 0;
        for (double value : sortedResponses) {
            if (value > settings.slaSeconds) {
                late++;
            }
        }
        return sortedResponses.length == 0 ? 0 : 100.0 * late / sortedResponses.length;
    }

    public int intervals() {
        return rows.size();
    }

    public int peakVms() {
        int peak = 0;
        for (Row row : rows) {
            peak = Math.max(peak, row.ready);
        }
        return peak;
    }

    public int readyVmsAt(int interval) {
        for (Row row : rows) {
            if (row.interval == interval) {
                return row.ready;
            }
        }
        return -1;
    }

    public String summaryLine() {
        int overloaded = 0;
        double memorySum = 0;
        double memoryPeak = 0;
        for (Row row : rows) {
            if (row.demand > row.capacity) {
                overloaded++;
            }
            double gb = row.ready * settings.vmRamMb / 1024.0;
            memorySum += gb;
            memoryPeak = Math.max(memoryPeak, gb);
        }
        double readyCapacityMi = readyVmSeconds * settings.vmMips;
        return String.format(Locale.ROOT, "%s,%s,%.2f,%.3f,%.3f,%.3f,%.4f,%.3f,%.3f,%.3f,%.3f,%d,%d,%d,%d,%d,%d,%.0f,%.0f,%.1f,%.2f",
                scenario.name, policy, settings.targetUtilization, billedVmSeconds / 3600, readyVmSeconds / 3600,
                100 * completedMi / readyCapacityMi, slaViolationPercent(), meanResponse(), percentile(0.95),
                percentile(0.99), percentile(1.0), overloaded, rows.size(), scaleUps, scaleDowns, peakVms(),
                failedVmCreations, submittedMi, completedMi, memoryPeak, memorySum / rows.size());
    }

    public List<String> intervalLines() {
        List<String> lines = new ArrayList<>(rows.size());
        for (Row row : rows) {
            double[] slot = responseByInterval.getOrDefault(row.interval, new double[3]);
            lines.add(String.format(Locale.ROOT, "%s,%s,%.2f,%d,%.1f,%.1f,%d,%d,%d,%.0f,%.2f,%.1f,%.2f,%.0f",
                    scenario.name, policy, settings.targetUtilization, row.interval, row.demand, row.planned, row.target,
                    row.ready, row.booting, row.capacity, 100 * row.demand / row.capacity,
                    row.ready * settings.vmRamMb / 1024.0, slot[1] == 0 ? 0 : slot[0] / slot[1], slot[2]));
        }
        return lines;
    }
}
