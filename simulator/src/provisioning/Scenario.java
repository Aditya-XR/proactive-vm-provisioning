package provisioning;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.List;

/** Demand and forecast series for one VM group on one day, indexed by interval. */
public final class Scenario {
    public final String name;
    public final double[] demandMips;
    public final double[] forecastMips;
    public final int firstInterval;
    public final int lastInterval;

    public Scenario(String name, double[] demandMips, double[] forecastMips, int firstInterval, int lastInterval) {
        this.name = name;
        this.demandMips = demandMips;
        this.forecastMips = forecastMips;
        this.firstInterval = firstInterval;
        this.lastInterval = lastInterval;
    }

    /** Reads a CSV with the header interval,demand_mips,forecast_mips. */
    public static Scenario load(Path file) throws IOException {
        List<String> lines = Files.readAllLines(file, StandardCharsets.UTF_8);
        int size = lines.size() - 1;
        double[] demand = new double[size];
        double[] forecast = new double[size];
        Arrays.fill(forecast, Double.NaN);
        int firstForecast = -1;
        for (int i = 0; i < size; i++) {
            String[] parts = lines.get(i + 1).trim().split(",");
            int interval = Integer.parseInt(parts[0]);
            demand[interval] = Double.parseDouble(parts[1]);
            if (parts.length > 2 && !parts[2].isEmpty()) {
                forecast[interval] = Double.parseDouble(parts[2]);
                if (firstForecast < 0) {
                    firstForecast = interval;
                }
            }
        }
        String base = file.getFileName().toString().replace(".csv", "");
        // A tick at interval t uses the forecast for t + 1, and the last tick also needs t + 1.
        return new Scenario(base, demand, forecast, firstForecast, size - 2);
    }

    public double peakDemand() {
        double peak = 0;
        for (int t = firstInterval; t <= lastInterval; t++) {
            peak = Math.max(peak, demandMips[t]);
        }
        return peak;
    }
}
