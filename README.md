# IoT Network - Wireless Architecture Best-Practices, Offensive Security Attacks, and Cloud Integration
- Designed a secure IoT network: wireless data collection, Wi-Fi security (WPA2/3) &amp; Wireshark analysis. Built a secure end-to-end solution: Raspberry Pi edge, TLS-FastAPI in Docker on Azure &amp; remote Dashboard. Applied network segmentation and secure MQTT to simulate enterprise & industrial deployments.
  
![WhatsApp Image 2026-04-01 at 15 12 03](https://github.com/user-attachments/assets/a2000c69-fec4-4c7e-aeaf-584b55cb3507)

- System Architecture
<img width="1671" height="866" alt="image" src="https://github.com/user-attachments/assets/6f792f96-69a5-4250-8789-76f4255ea594" />

To implement and analyze this infrastructure, the initial baseline data was structured across four logical layers, aligned with large-scale architectures.
At the data acquisition layer, an ESP32 development board connected to a DHT-22 sensor was utilized, which is responsible for reading environmental metrics. The wireless radio transmission is captured via Wi-Fi by a local Raspberry Pi 5 gateway/router running a Mosquitto MQTT message broker.
Standard WPA2 and WPA3 security protocols were tested between these two segments, evaluating network intrusion methods from the perspective of an external attacker. To guarantee data confidentiality even in the event of a compromised Wi-Fi network, a local Public Key Infrastructure (PKI) was implemented, integrating application-level TLS encryption through unique digital certificates that validate the connection between the ESP32 and the Raspberry Pi.
Extending the network layer, the physical security of the infrastructure was also studied, given that the wireless network is directly connected to it. Through virtualization on a Proxmox server, a pfSense-based perimeter firewall was created to protect the laboratory network, while simultaneously providing remote equipment configuration capabilities via a secure VPN tunnel.
In the Cloud tier, data is transmitted asynchronously to Microsoft Azure services, where the data history is saved in a NoSQL database (Cosmos DB) and analyzed in the background by an artificial intelligence algorithm (Isolation Forest) for operational anomaly detection.
The application layer centralizes all this information into a customized web dashboard, allowing operators to monitor the current status of network equipment and send secure commands back to the field.


