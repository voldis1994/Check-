class CheckTraderError(Exception): pass
class ConfigurationError(CheckTraderError): pass
class DataError(CheckTraderError): pass
class BridgeError(CheckTraderError): pass
