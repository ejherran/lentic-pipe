from prometheus_client import Gauge

runs_pending = Gauge("lentic_runs_pending", "Training runs currently queued (pending)")
runs_running = Gauge("lentic_runs_running", "Training runs currently being processed")
simulations_pending = Gauge("lentic_simulations_pending", "Simulations currently queued (pending)")
simulations_running = Gauge("lentic_simulations_running", "Simulations currently being processed")
