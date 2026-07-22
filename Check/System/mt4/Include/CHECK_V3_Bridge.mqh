// CHECK SYSTEM v3 bridge directory layout.
#ifndef CHECK_V3_BRIDGE_MQH
#define CHECK_V3_BRIDGE_MQH

#include "CHECK_V3_Protocol.mqh"

string CHECK_V3_ROOT_DIR = "";
string CHECK_V3_RUNTIME_DIR = "";
string CHECK_V3_BRIDGE_DIR = "";
string CHECK_V3_MARKET_DIR = "";
string CHECK_V3_STATUS_DIR = "";
string CHECK_V3_COMMANDS_DIR = "";
string CHECK_V3_ACK_DIR = "";
string CHECK_V3_ARCHIVE_DIR = "";

string CheckV3DefaultRoot()
{
   return CheckV3PathJoin(TerminalInfoString(TERMINAL_DATA_PATH), "MQL4\\Files\\CHECK_SYSTEM");
}

bool CheckV3ResolveBridge(string requestedRoot)
{
   if(StringLen(requestedRoot) == 0)
   {
      string dataPath = TerminalInfoString(TERMINAL_DATA_PATH);
      if(StringLen(dataPath) == 0)
         return false;
      CHECK_V3_ROOT_DIR = CheckV3PathJoin(dataPath, "MQL4\\Files\\CHECK_SYSTEM");
   }
   else
      CHECK_V3_ROOT_DIR = CheckV3NormalizePath(requestedRoot);

   if(StringLen(CHECK_V3_ROOT_DIR) == 0)
      return false;

   CHECK_V3_RUNTIME_DIR = CheckV3PathJoin(CHECK_V3_ROOT_DIR, "runtime");
   CHECK_V3_BRIDGE_DIR = CheckV3PathJoin(CHECK_V3_RUNTIME_DIR, "bridge");
   CHECK_V3_MARKET_DIR = CheckV3PathJoin(CHECK_V3_BRIDGE_DIR, "market");
   CHECK_V3_STATUS_DIR = CheckV3PathJoin(CHECK_V3_BRIDGE_DIR, "status");
   CHECK_V3_COMMANDS_DIR = CheckV3PathJoin(CHECK_V3_BRIDGE_DIR, "commands");
   CHECK_V3_ACK_DIR = CheckV3PathJoin(CHECK_V3_BRIDGE_DIR, "acknowledgements");
   CHECK_V3_ARCHIVE_DIR = CheckV3PathJoin(CHECK_V3_BRIDGE_DIR, "archive");
   return true;
}

bool CheckV3EnsureBridgeDirs()
{
   return CheckV3EnsureDir(CHECK_V3_ROOT_DIR) &&
          CheckV3EnsureDir(CHECK_V3_RUNTIME_DIR) &&
          CheckV3EnsureDir(CHECK_V3_BRIDGE_DIR) &&
          CheckV3EnsureDir(CHECK_V3_MARKET_DIR) &&
          CheckV3EnsureDir(CHECK_V3_STATUS_DIR) &&
          CheckV3EnsureDir(CHECK_V3_COMMANDS_DIR) &&
          CheckV3EnsureDir(CHECK_V3_ACK_DIR) &&
          CheckV3EnsureDir(CHECK_V3_ARCHIVE_DIR);
}

string CheckV3BridgePathForComment()
{
   return CHECK_V3_ROOT_DIR;
}

#endif
