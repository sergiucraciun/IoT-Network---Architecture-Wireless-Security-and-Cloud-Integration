# IoT Network - Wireless Architecture Best-Practices, Offensive Security Attacks, and Cloud Integration

  The project stems from the critical requirement to secure data flows in modern engineering, where the monitoring of operational metrics relies heavily on smart electronic modules with limited resources and wireless network transmissions. While the current configuration reads temperature and humidity data, the architecture was designed to be entirely independent of the specific sensors or hardware devices used; environmental testing merely serves as a practical use case to validate a secure communication tunnel.
  A cyber attack targeting the radio transmissions of these circuits could lead to unauthorized external commands or the interception and tampering of technical data. To address this risk, a modular system was developed that can be rapidly replicated across various industry scenarios. In industrial environments, the system can ensure the remote startup or shutdown of an electric motor or a conveyor belt based on automated alerts. Meanwhile, in a residential context or a smart home setup, the exact same architecture can control access gates, adjust climate control settings remotely, or stream real-time video from a wireless camera to a mobile application.
  
![WhatsApp Image 2026-04-01 at 15 12 03](https://github.com/user-attachments/assets/a2000c69-fec4-4c7e-aeaf-584b55cb3507)

- System Architecture

To implement and analyze this infrastructure, the initial baseline data was structured across four logical layers, aligned with large-scale architectures.
  
<img width="1671" height="866" alt="image" src="https://github.com/user-attachments/assets/6f792f96-69a5-4250-8789-76f4255ea594" />
  
  At the data acquisition layer, an ESP32 development board connected to a DHT-22 sensor was utilized, which is responsible for reading environmental metrics. The wireless radio transmission is captured via Wi-Fi by a local Raspberry Pi 5 gateway/router running a Mosquitto MQTT message broker. Standard WPA2 and WPA3 security protocols were tested between these two segments, evaluating network intrusion methods from the perspective of an external attacker. To guarantee data confidentiality even in the event of a compromised Wi-Fi network, a local Public Key Infrastructure (PKI) was implemented, integrating application-level TLS encryption through unique digital certificates that validate the connection between the ESP32 and the Raspberry Pi.
  Extending the network layer, the physical security of the infrastructure was also studied, given that the wireless network is directly connected to it. Through virtualization on a Proxmox server, a pfSense-based perimeter firewall was created to protect the laboratory network, while simultaneously providing remote equipment configuration capabilities via a secure VPN tunnel.
  In the Cloud tier, data is transmitted asynchronously to Microsoft Azure services, where the data history is saved in a NoSQL database (Cosmos DB) and analyzed in the background by an artificial intelligence algorithm (Isolation Forest) for operational anomaly detection.
  The application layer centralizes all this information into a customized web dashboard, allowing operators to monitor the current status of network equipment and send secure commands back to the field.


- Local Network Architecture
  
<img width="1458" height="581" alt="image" src="https://github.com/user-attachments/assets/c956ab97-e4ed-415c-ad90-923e41ffca38" />

- Cloud Architecture

<img width="1459" height="754" alt="image" src="https://github.com/user-attachments/assets/06fd2328-3473-4075-84ac-48668cdaab5e" />

- NoSQL Database

<img width="1460" height="791" alt="image" src="https://github.com/user-attachments/assets/5d353e7a-33e5-42da-85ff-2933db71979c" />

- AI Training

<img width="1408" height="698" alt="image" src="https://github.com/user-attachments/assets/58b9d4e4-7a43-4961-ae82-a5e0421df918" />
