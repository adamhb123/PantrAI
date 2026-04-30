// Backend runs on the host machine. 10.0.2.2 routes to localhost on Android emulator.
// Change this to your machine's IP when running on a physical device.
const String kBackendBaseUrl = 'https://pok-unsnared-krystina.ngrok-free.dev';

const int kBarcodeScanThreshold = 5;

const Duration kApiTimeout = Duration(seconds: 2000);
