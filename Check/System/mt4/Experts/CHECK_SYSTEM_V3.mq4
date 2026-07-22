// CHECK SYSTEM v3 MT4 bridge EA.
// Exports market/status JSON and executes Python-generated command JSON only.
#property copyright "Check System"
#property link      "https://github.com/voldis1994/Check-"
#property version   "3.00"
#property strict

// Quoted includes resolve next to this EA (MQL4\Experts\) after DEPLOY_MT4.
#include "CHECK_V3_Protocol.mqh"
#include "CHECK_V3_Bridge.mqh"
#include "CHECK_V3_Market.mqh"
#include "CHECK_V3_Execution.mqh"

input int MagicNumber = 3003001;
// Empty = AUTO -> TerminalDataPath\MQL4\Files\CHECK_SYSTEM
input string BridgeRootPath = "";

datetime CHECK_V3_LAST_EXPORT_AT = 0;
bool CHECK_V3_LAST_EXPORT_OK = false;

void CheckV3SetChartComment()
{
   string exportState = CHECK_V3_LAST_EXPORT_OK ? "EXPORT OK" : "EXPORT FAIL";
   string age = CHECK_V3_LAST_EXPORT_AT > 0
      ? IntegerToString((int)(TimeCurrent() - CHECK_V3_LAST_EXPORT_AT)) + "s ago"
      : "never";
   Comment("CHECK SYSTEM v3.0.1\n",
           "Bridge: ", CheckV3BridgePathForComment(), "\n",
           "Protocol: ", CHECK_V3_PROTOCOL_VERSION, "\n",
           exportState, " (", age, ")\n",
           "Files must update every ~1s. If EXPORT FAIL: Allow DLL imports.");
}

bool CheckV3ExportAndExecute()
{
   bool marketOk = CheckV3ExportMarket(MagicNumber);
   bool statusOk = CheckV3ExportStatus(MagicNumber);
   CheckV3ExecuteCommands(MagicNumber);
   CHECK_V3_LAST_EXPORT_OK = marketOk && statusOk;
   if(CHECK_V3_LAST_EXPORT_OK)
      CHECK_V3_LAST_EXPORT_AT = TimeCurrent();
   CheckV3SetChartComment();
   return CHECK_V3_LAST_EXPORT_OK;
}

int OnInit()
{
   if(Period() != PERIOD_M1)
   {
      Alert("CHECK SYSTEM v3 requires an M1 chart. Attach CHECK_SYSTEM_V3 to M1 only.");
      return(INIT_FAILED);
   }

   if(!CheckV3ResolveBridge(BridgeRootPath))
   {
      Alert("CHECK SYSTEM v3: cannot resolve BridgeRootPath / TERMINAL_DATA_PATH");
      return(INIT_FAILED);
   }

   if(!CheckV3EnsureBridgeDirs())
   {
      Alert("CHECK SYSTEM v3: failed to create bridge directories. Enable Allow DLL imports.");
      return(INIT_FAILED);
   }

   EventSetMillisecondTimer(500);
   CheckV3ExportAndExecute();
   Print(
      "CHECK_SYSTEM_V3 initialized bridge=", CheckV3BridgePathForComment(),
      " magic=", MagicNumber,
      " account=", AccountNumber()
   );
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
