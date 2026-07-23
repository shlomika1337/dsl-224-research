#include <SoftwareSerial.h>

#define ROUTER_RX   D2    // GPIO4 <- router TX
#define ROUTER_TX   D1    // GPIO5 -> router RX
#define ROUTER_BAUD 115200
#define PC_BAUD     115200

SoftwareSerial router;

void setup() {
  Serial.begin(PC_BAUD);
  router.begin(ROUTER_BAUD, SWSERIAL_8N1, ROUTER_RX, ROUTER_TX, false, 512);
  delay(200);
  Serial.println("\n[bridge up]");   // proves sketch runs + USB link + PC baud
}

void loop() {
  while (router.available()) Serial.write(router.read());
  while (Serial.available()) router.write(Serial.read());
}
