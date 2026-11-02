package provisioning;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.LinkedList;
import java.util.List;

import org.cloudbus.cloudsim.Datacenter;
import org.cloudbus.cloudsim.DatacenterCharacteristics;
import org.cloudbus.cloudsim.Host;
import org.cloudbus.cloudsim.Log;
import org.cloudbus.cloudsim.Pe;
import org.cloudbus.cloudsim.Storage;
import org.cloudbus.cloudsim.VmAllocationPolicySimple;
import org.cloudbus.cloudsim.VmSchedulerTimeShared;
import org.cloudbus.cloudsim.core.CloudSim;
import org.cloudbus.cloudsim.provisioners.BwProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.PeProvisionerSimple;
import org.cloudbus.cloudsim.provisioners.RamProvisionerSimple;

/** Builds one CloudSim datacenter and runs a single scenario under a single policy. */
public final class Simulation {
    private Simulation() {
    }

    public static RunResult run(Scenario scenario, Policy policy, Settings settings, double margin) throws Exception {
        Log.disable();
        CloudSim.init(1, Calendar.getInstance(), false);
        buildDatacenter(settings);
        ProvisioningBroker broker = new ProvisioningBroker("Broker", scenario, policy, settings, margin);
        CloudSim.startSimulation();
        CloudSim.stopSimulation();
        return broker.result();
    }

    private static Datacenter buildDatacenter(Settings settings) throws Exception {
        List<Host> hosts = new ArrayList<>();
        for (int h = 0; h < settings.hosts; h++) {
            List<Pe> pes = new ArrayList<>();
            for (int c = 0; c < settings.hostCores; c++) {
                pes.add(new Pe(c, new PeProvisionerSimple(settings.vmMips)));
            }
            hosts.add(new Host(h, new RamProvisionerSimple(settings.hostRamMb), new BwProvisionerSimple(settings.hostBwMbps),
                    settings.hostStorageMb, pes, new VmSchedulerTimeShared(pes)));
        }
        DatacenterCharacteristics characteristics = new DatacenterCharacteristics("x86", "Linux", "Xen", hosts,
                10.0, 3.0, 0.05, 0.001, 0.0);
        return new Datacenter("Datacenter", characteristics, new VmAllocationPolicySimple(hosts), new LinkedList<Storage>(), 0);
    }
}
