// CHECK SYSTEM v3 MT4 bridge EA.
// Exports market/status JSON and executes Python-generated command JSON only.
#property copyright "Check System"
#property link      "https://github.com/voldis1994/Check-"
#property version   "3.0.0"
#property strict

// Quoted includes resolve next to this EA (MQL4\Experts\) after DEPLOY_MT4.
// Angle-bracket includes also work if the same files are in MQL4\Include\.
#include "CHECK_V3_Protocol.mqh"
#include "CHECK_V3_Bridge.mqh"
#include "CHECK_V3_Market.mqh"
#include "CHECK_V3_Execution.mqh"

input int MagicNumber = 3003001;
// Empty = AUTO -> TerminalDataPath\MQL4\Files\CHECK_SYSTEM
input string BridgeRootPath = "";

void CheckV3SetChartComment()
{
   Comment("CHECK SYSTEM v3.0.0\n",
           "Bridge: ", CheckV3BridgePathForComment(), "\n",
           "Protocol: ", CHECK_V3_PROTOCOL_VERSION, "\n",
           "EA is transport only; strategy runs outside MT4.");
}

bool CheckV3ExportAndExecute()
{
   bool marketOk = CheckV3ExportMarket(MagicNumber);
   bool statusOk = CheckV3ExportStatus(MagicNumber);
   CheckV3ExecuteCommands(MagicNumber);
   CheckV3SetChartComment();
   return marketOk && statusOk;
}

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Alert("CHECK SYSTEM v3 requires an M1 chart. Attach CHECK_SYSTEM_V3 to M1 only.");
      return(INIT_FAILED);
   }

   string root = CheckV3ResolveBridge(BridgeRootPath);
   if(StringLen(root) == 0)
   {
      Alert("CHECK SYSTEM v3: cannot resolve BridgeRootPath / TERMINAL_DATA_PATH");
      return(INIT_FAILED);
   }

   if(!CheckV3EnsureBridgeDirs(root))
   {
      Alert("CHECK SYSTEM v3: failed to create bridge directories. Enable Allow DLL imports.");
      return(INIT_FAILED);
   }

   EventSetMillisecondTimer(500);
   CheckV3ExportAndExecute();
   Print("CHECK_SYSTEM_V3 initialized bridge=", root, " magic=", MagicNumber, " account=", AccountNumber());
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Comment("");
}

void OnTimer()
{
   CheckV3ExportAndExecute();
}

void OnTick()
{
   CheckV3ExportAndExecute();
}
