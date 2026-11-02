package provisioning;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Deque;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.cloudbus.cloudsim.Cloudlet;
import org.cloudbus.cloudsim.CloudletSchedulerTimeShared;
import org.cloudbus.cloudsim.DatacenterBroker;
import org.cloudbus.cloudsim.UtilizationModel;
import org.cloudbus.cloudsim.UtilizationModelFull;
import org.cloudbus.cloudsim.Vm;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.core.CloudSimTags;
import org.cloudbus.cloudsim.core.SimEvent;

/**
 * Scales a pool of identical worker VMs while the simulation runs.
 *
 * Every 300 s (a tick) the broker picks a target VM count for the next interval
 * and starts or drains VMs. Every 60 s (a slice) it splits one minute of demand
 * equally across the ready VMs as cloudlets. A VM that cannot keep up builds a
 * real queue inside CloudSim, which shows up as a longer response time.
 */
public class ProvisioningBroker extends DatacenterBroker {
    static final int TICK = 900_001;
    static final int SLICE = 900_002;

    private final Scenario scenario;
    private final Policy policy;
    private final Settings settings;
    private final double margin;

    private final Map<Integer, Vm> ready = new LinkedHashMap<>();
    private final Map<Integer, Vm> booting = new HashMap<>();
    private final Set<Integer> draining = new HashSet<>();
    private final Map<Integer, Integer> outstanding = new HashMap<>();
    private final Map<Integer, Double> requestedAt = new HashMap<>();
    private final Map<Integer, Double> readyAt = new HashMap<>();
    private final Map<Integer, Double> dispatchTime = new HashMap<>();
    private final Map<Integer, Integer> cloudletInterval = new HashMap<>();
    private final Deque<Integer> recentTargets = new ArrayDeque<>();
    private final UtilizationModel full = new UtilizationModelFull();
    private final List<Double> responses = new ArrayList<>();

    private final RunResult result;
    private int datacenterId;
    private int nextVmId;
    private int nextCloudletId;
    private int openCloudlets;
    private int interval;
    private int sliceInInterval;
    private boolean finishedDispatch;

    public ProvisioningBroker(String name, Scenario scenario, Policy policy, Settings settings, double margin) throws Exception {
        super(name);
        this.scenario = scenario;
        this.policy = policy;
        this.settings = settings;
        this.margin = margin;
        this.interval = scenario.firstInterval;
        this.result = new RunResult(scenario, policy, settings);
    }

    public RunResult result() {
        return result;
    }

    @Override
    protected void createVmsInDatacenter(int id) {
        datacenterId = id;
        int initial = policy == Policy.STATIC_PEAK
                ? vmsFor(scenario.peakDemand())
                : vmsFor(scenario.demandMips[interval - 1]);
        for (int i = 0; i < initial; i++) {
            requestVm(0.0);
        }
        recentTargets.add(initial);
        schedule(getId(), 1.0, TICK);
    }

    private int vmsFor(double demandMips) {
        int vms = (int) Math.ceil(demandMips / (settings.vmMips * settings.targetUtilization));
        return Math.max(settings.minVms, Math.min(settings.maxVms, vms));
    }

    private void requestVm(double delay) {
        int id = nextVmId++;
        Vm vm = new Vm(id, getId(), settings.vmMips, 1, settings.vmRamMb, settings.vmBwMbps, settings.vmImageMb,
                "Xen", new CloudletSchedulerTimeShared());
        booting.put(id, vm);
        outstanding.put(id, 0);
        requestedAt.put(id, CloudSim.clock());
        send(datacenterId, delay, CloudSimTags.VM_CREATE_ACK, vm);
    }

    @Override
    protected void processVmCreate(SimEvent ev) {
        int[] data = (int[]) ev.getData();
        Vm vm = booting.remove(data[1]);
        if (data[2] == CloudSimTags.TRUE) {
            ready.put(vm.getId(), vm);
            readyAt.put(vm.getId(), CloudSim.clock());
        } else {
            result.failedVmCreations++;
        }
    }

    /** Demand the policy plans for: the interval after next, with data up to the last interval. */
    private double plannedDemand() {
        int target = interval + 1;
        switch (policy) {
            case REACTIVE:
                return scenario.demandMips[interval - 1];
            case PROACTIVE:
                return scenario.forecastMips[target];
            case PROACTIVE_MARGIN:
                return scenario.forecastMips[target] * (1 + margin);
            case ORACLE:
                return scenario.demandMips[target];
            default:
                return scenario.peakDemand();
        }
    }

    private void onTick() {
        double planned = plannedDemand();
        int target = vmsFor(planned);
        recentTargets.addLast(target);
        while (recentTargets.size() > settings.scaleInTicks) {
            recentTargets.removeFirst();
        }

        int pool = ready.size() - draining.size() + booting.size();
        if (policy != Policy.STATIC_PEAK) {
            if (target > pool) {
                for (int i = pool; i < target; i++) {
                    requestVm(settings.bootDelaySeconds);
                }
                result.scaleUps++;
            } else if (recentTargets.size() == settings.scaleInTicks) {
                int keep = recentTargets.stream().mapToInt(Integer::intValue).max().getAsInt();
                if (keep < pool) {
                    drain(pool - keep);
                    result.scaleDowns++;
                }
            }
        }

        double demand = scenario.demandMips[interval];
        double capacity = (ready.size() - draining.size()) * settings.vmMips;
        result.addInterval(interval, demand, planned, target, ready.size() - draining.size(), booting.size(), capacity);
        sliceInInterval = 0;
        onSlice();
    }

    private void drain(int count) {
        List<Integer> candidates = new ArrayList<>();
        for (Integer id : ready.keySet()) {
            if (!draining.contains(id)) {
                candidates.add(id);
            }
        }
        // Newest first, so the oldest VMs stay and billing stays simple.
        for (int i = candidates.size() - 1; i >= 0 && count > 0; i--, count--) {
            int id = candidates.get(i);
            draining.add(id);
            if (outstanding.get(id) == 0) {
                destroy(id);
            }
        }
    }

    private void destroy(int id) {
        Vm vm = ready.remove(id);
        draining.remove(id);
        sendNow(datacenterId, CloudSimTags.VM_DESTROY, vm);
        closeVmAccount(id);
    }

    private void closeVmAccount(int id) {
        double now = CloudSim.clock();
        result.billedVmSeconds += now - requestedAt.get(id);
        result.readyVmSeconds += now - readyAt.get(id);
    }

    private void onSlice() {
        List<Integer> active = new ArrayList<>();
        for (Integer id : ready.keySet()) {
            if (!draining.contains(id)) {
                active.add(id);
            }
        }
        double work = scenario.demandMips[interval] * settings.sliceSeconds;
        long length = Math.max(1L, Math.round(work / active.size()));
        for (Integer vmId : active) {
            Cloudlet cloudlet = new Cloudlet(nextCloudletId++, length, 1, 300, 300, full, full, full);
            cloudlet.setUserId(getId());
            cloudlet.setVmId(vmId);
            dispatchTime.put(cloudlet.getCloudletId(), CloudSim.clock());
            cloudletInterval.put(cloudlet.getCloudletId(), interval);
            outstanding.merge(vmId, 1, Integer::sum);
            openCloudlets++;
            result.submittedMi += length;
            sendNow(datacenterId, CloudSimTags.CLOUDLET_SUBMIT, cloudlet);
        }

        sliceInInterval++;
        if (sliceInInterval < settings.slicesPerInterval) {
            schedule(getId(), settings.sliceSeconds, SLICE);
        } else if (interval < scenario.lastInterval) {
            interval++;
            schedule(getId(), settings.sliceSeconds, TICK);
        } else {
            finishedDispatch = true;
        }
    }

    @Override
    protected void processCloudletReturn(SimEvent ev) {
        Cloudlet cloudlet = (Cloudlet) ev.getData();
        double response = CloudSim.clock() - dispatchTime.remove(cloudlet.getCloudletId());
        int vmId = cloudlet.getVmId();
        int origin = cloudletInterval.remove(cloudlet.getCloudletId());
        responses.add(response);
        result.addResponse(origin, response);
        result.completedMi += cloudlet.getCloudletLength();
        outstanding.merge(vmId, -1, Integer::sum);
        openCloudlets--;

        if (draining.contains(vmId) && outstanding.get(vmId) == 0) {
            destroy(vmId);
        }
        if (finishedDispatch && openCloudlets == 0) {
            for (Integer id : new ArrayList<>(ready.keySet())) {
                sendNow(datacenterId, CloudSimTags.VM_DESTROY, ready.get(id));
                closeVmAccount(id);
            }
            ready.clear();
            draining.clear();
            result.setResponses(toSortedArray(responses));
            finishExecution();
        }
    }

    private static double[] toSortedArray(List<Double> values) {
        double[] out = new double[values.size()];
        for (int i = 0; i < out.length; i++) {
            out[i] = values.get(i);
        }
        Arrays.sort(out);
        return out;
    }

    @Override
    protected void processOtherEvent(SimEvent ev) {
        switch (ev.getTag()) {
            case TICK:
                onTick();
                break;
            case SLICE:
                onSlice();
                break;
            case CloudSimTags.VM_DESTROY_ACK:
                break;
            default:
                super.processOtherEvent(ev);
        }
    }
}
