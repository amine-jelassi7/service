package main

import (
	"encoding/json"
	"log"
	"net/http"
	"runtime"
)

type PredictRequest struct {
	Instances []map[string]interface{} `json:"instances"`
}

type PredictResponse struct {
	Predictions []Prediction `json:"predictions"`
}

type Prediction struct {
	ID         interface{} `json:"ID"`
	Prediction float64     `json:"prediction"`
}

var pool *WorkerPool
var healthy bool

func main() {
	numWorkers := runtime.NumCPU()
	log.Printf("[main] Starting %d Python workers...", numWorkers)

	pool = NewWorkerPool(numWorkers)
	pool.Start() // blocks until all workers are READY

	healthy = true
	log.Printf("[main] All %d workers ready. Listening on :8080", numWorkers)

	mux := http.NewServeMux()
	mux.HandleFunc("/health", healthHandler)
	mux.HandleFunc("/predict", predictHandler)

	srv := &http.Server{
		Addr:    ":8080",
		Handler: mux,
	}
	log.Fatal(srv.ListenAndServe())
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	if !healthy {
		w.WriteHeader(http.StatusServiceUnavailable)
		w.Write([]byte(`{"status":"not ready"}`))
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.Write([]byte(`{"status":"ok"}`))
}

func predictHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req PredictRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "bad request: "+err.Error(), http.StatusBadRequest)
		return
	}
	if len(req.Instances) == 0 {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"predictions":[]}`))
		return
	}

	resp, err := pool.Dispatch(req)
	if err != nil {
		log.Printf("[predict] dispatch error: %v", err)
		http.Error(w, "inference error", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(resp)
}
