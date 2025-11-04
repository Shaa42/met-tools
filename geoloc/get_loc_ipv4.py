import json
import subprocess
from time import sleep


def callBash(scriptName: str):
    _ = subprocess.run(["bash", scriptName], text=True, capture_output=True)


def getRouters(fname: str):
    print("Calling script...")
    _ = subprocess.run(
        ["bash", "resolve_ip_traceroute.sh", fname], text=True, capture_output=True
    )
    sleep(1)
    print("Done.")


if __name__ == "__main__":
    resolve = True
    fname_ext = "out"
    if resolve:
        getRouters(fname_ext)
    fname = "assets/trcrt-out/fanrt_" + fname_ext + ".txt"

    callBash("create_dir.sh")

    ip_list: list[str] = []
    with open(fname, "r") as file:
        for line in file:
            ip = line.strip()
            if ip and ip not in ip_list:
                ip_list.append(ip.strip("*"))

    # print(ip_list)

    loc_dict = {}
    for ip in ip_list:
        # Call ipinfo.io API
        json_output = subprocess.run(
            ["bash"], input=f"curl ipinfo.io/{ip}", text=True, capture_output=True
        ).stdout

        # print(json_output)

        # Get "loc" value and put it in loc_list
        data = json.loads(json_output)
        if "loc" in data:
            loc_dict[ip] = data["loc"]
        else:
            print(f"Didn't add loc of : {data['ip']}")

    # print("List of the localisations of each IPv4 address of the traceroute :")
    # print(loc_dict)

    # Create CSV file based on loc_dict
    print("Creating CSV file...")
    with open("assets/csv/loc_ipv4_fandom.csv", "w") as file:
        file.write("ip,latitude,longitude\n")
        for ip, loc in loc_dict.items():
            file.write(f"{ip},{loc}\n")
    print("Done.")
