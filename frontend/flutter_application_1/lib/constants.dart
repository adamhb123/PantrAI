// Backend runs on the host machine. 10.0.2.2 routes to localhost on Android emulator.
// Change this to your machine's IP when running on a physical device.
const String kBackendBaseUrl = 'http://10.0.2.2:8000';

const int kBarcodeScanThreshold = 10;

const Duration kApiTimeout = Duration(seconds: 30);
