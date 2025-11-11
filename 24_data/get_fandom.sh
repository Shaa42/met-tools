#!/usr/bin/bash

OUTPUT_FILE="perf-data/$(date +"%s")_perf.json"

curl -o /dev/null -s -w '{
    "url": "%{url_effective}",
    "dns_lookup_time": %{time_namelookup},
    "tcp_connect_time": %{time_connect},
    "tls_handshake_time": %{time_appconnect},
    "time_to_first_byte": %{time_starttransfer},
    "total_time": %{time_total},
    "redirects": %{num_redirects},
    "size_downloaded": %{size_download}
}\n' https://www.fandom.com > "$OUTPUT_FILE"
