// CHECK SYSTEM v3 MT4 bridge EA.
// Exports market/status JSON and executes Python-generated command JSON only.
#property strict

#include <CHECK_V3_Protocol.mqh>
#include <CHECK_V3_Bridge.mqh>
#include <CHECK_V3_Market.mqh>
#include <CHECK_V3_Execution.mqh>

input int MagicNumber = 3003001;
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
   MathSrand(GetTickCount());

   if(Period() != PERIOD_M1)
   {
      Alert("CHECK SYSTEM v3 requires an M1 chart. Attach CHECK_SYSTEM_V3 to M1 only.");
      return INIT_FAILED;
   }

   if(!IsDllsAllowed())
   {
      Alert("CHECK SYSTEM v3 requires Allow DLL imports for kernel32 path operations.");
      return INIT_FAILED;
   }

   CheckV3ResolveBridge(BridgeRootPath);
   if(!CheckV3EnsureBridgeDirs())
   {
      Alert("CHECK SYSTEM v3 could not create bridge directories: ", CheckV3BridgePathForComment());
      return INIT_FAILED;
   }

   EventSetMillisecondTimer(500);
   CheckV3ExportAndExecute(); // smoke export on startup
   CheckV3SetChartComment();
   Print("CHECK SYSTEM v3 initialized. bridge=", CheckV3BridgePathForComment());
   return INIT_SUCCEEDED;
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
