name="$1"

sudo traceroute -n --tcp --sendwait=0.5 fandom.com | tail -n+2 | awk '{ ip=""; for(i=1;i<=NF;i++) if ($i ~ /^([0-9]{1,3}\.){3}[0-9]{1,3}$/) { ip=$i; break } print ip }' > assets/trcrt-out/fanrt_"$name".txt
