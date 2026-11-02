package provisioning;

import java.io.BufferedWriter;
import java.nio.charset.StandardCharsets;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/** Runs every scenario under every policy and target utilization. */
public final class Main {
    private static final double[] TARGETS = {0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95};

    private Main() {
    }

    public static void main(String[] args) throws Exception {
        Path scenarioDir = Paths.get(args[0]);
        Path outDir = Paths.get(args[1]);
        double margin = Double.parseDouble(args[2]);

        List<Path> files = new ArrayList<>();
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(scenarioDir, "*.csv")) {
            stream.forEach(files::add);
        }
        Collections.sort(files);

        long start = System.nanoTime();
        int runs = 0;
        try (BufferedWriter summary = Files.newBufferedWriter(outDir.resolve("sim_summary.csv"), StandardCharsets.UTF_8);
                BufferedWriter intervals = Files.newBufferedWriter(outDir.resolve("sim_intervals.csv"), StandardCharsets.UTF_8)) {
            summary.write(RunResult.SUMMARY_HEADER);
            summary.newLine();
            intervals.write(RunResult.INTERVAL_HEADER);
            intervals.newLine();
            for (Path file : files) {
                Scenario scenario = Scenario.load(file);
                for (double target : TARGETS) {
                    Settings settings = new Settings().withTarget(target);
                    for (Policy policy : Policy.values()) {
                        RunResult result = Simulation.run(scenario, policy, settings, margin);
                        summary.write(result.summaryLine());
                        summary.newLine();
                        for (String line : result.intervalLines()) {
                            intervals.write(line);
                            intervals.newLine();
                        }
                        runs++;
                    }
                }
                System.out.printf("%s done (%d runs so far)%n", scenario.name, runs);
            }
        }
        System.out.printf("%d runs in %.1f s%n", runs, (System.nanoTime() - start) / 1e9);
    }
}
