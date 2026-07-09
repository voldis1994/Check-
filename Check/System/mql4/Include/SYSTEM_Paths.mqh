#ifndef __SYSTEM_PATHS_MQH__
#define __SYSTEM_PATHS_MQH__

#property strict

#include "SYSTEM_RootConfig.mqh"

#define SYSTEM_CLIENTS_RELATIVE_PATH "data\\clients"
#define SYSTEM_LOGS_RELATIVE_PATH "data\\logs"
#define SYSTEM_CACHE_RELATIVE_PATH "data\\cache"
#define SYSTEM_HISTORY_RELATIVE_PATH "data\\history"
#define SYSTEM_UNIVERSE_RELATIVE_PATH "data\\universe"
#define SYSTEM_ACCOUNT_JOURNAL_DIRNAME "journal"
#define SYSTEM_ACCOUNT_STATE_DIRNAME "state"

#define SYSTEM_INVALID_FILE_ATTRIBUTES -1
#define SYSTEM_FILE_ATTRIBUTE_DIRECTORY 16
#define SYSTEM_ERROR_ALREADY_EXISTS 183

#import "kernel32.dll"
   int GetFileAttributesW(string lpFileName);
   int CreateDirectoryW(string lpPathName, int lpSecurityAttributes);
#import

string g_system_root_override = "";

void SYSTEM_ConfigureRootPath(const string root_path)
{
   if(StringLen(root_path) > 0)
      g_system_root_override = root_path;
}

string SYSTEM_GetRootPath()
{
   if(StringLen(g_system_root_override) > 0)
      return g_system_root_override;
   return SYSTEM_ROOT_PATH;
}

string SYSTEM_GetClientsRelativePath()
{
   return SYSTEM_CLIENTS_RELATIVE_PATH;
}

string SYSTEM_GetLogsRelativePath()
{
   return SYSTEM_LOGS_RELATIVE_PATH;
}

string SYSTEM_GetCacheRelativePath()
{
   return SYSTEM_CACHE_RELATIVE_PATH;
}

string SYSTEM_GetHistoryRelativePath()
{
   return SYSTEM_HISTORY_RELATIVE_PATH;
}

string SYSTEM_GetUniverseRelativePath()
{
   return SYSTEM_UNIVERSE_RELATIVE_PATH;
}

string SYSTEM_JoinPath(const string left, const string right)
{
   if(StringLen(left) == 0)
      return right;
   if(StringLen(right) == 0)
      return left;

   string normalized_left = left;
   string normalized_right = right;
   int left_len = StringLen(normalized_left);
   if(StringGetCharacter(normalized_left, left_len - 1) == '\\')
      normalized_left = StringSubstr(normalized_left, 0, left_len - 1);

   if(StringGetCharacter(normalized_right, 0) == '\\')
      normalized_right = StringSubstr(normalized_right, 1);

   return normalized_left + "\\" + normalized_right;
}

string SYSTEM_BuildClientsDir()
{
   return SYSTEM_JoinPath(SYSTEM_GetRootPath(), SYSTEM_GetClientsRelativePath());
}

string SYSTEM_BuildAccountDir(const string account_id)
{
   return SYSTEM_JoinPath(SYSTEM_BuildClientsDir(), account_id);
}

string SYSTEM_BuildAccountJournalDir(const string account_id)
{
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), SYSTEM_ACCOUNT_JOURNAL_DIRNAME);
}

string SYSTEM_BuildAccountStateDir(const string account_id)
{
   return SYSTEM_JoinPath(SYSTEM_BuildAccountDir(account_id), SYSTEM_ACCOUNT_STATE_DIRNAME);
}

string SYSTEM_BuildLogsDir()
{
   return SYSTEM_JoinPath(SYSTEM_GetRootPath(), SYSTEM_GetLogsRelativePath());
}

string SYSTEM_BuildCacheDir()
{
   return SYSTEM_JoinPath(SYSTEM_GetRootPath(), SYSTEM_GetCacheRelativePath());
}

string SYSTEM_BuildHistoryDir()
{
   return SYSTEM_JoinPath(SYSTEM_GetRootPath(), SYSTEM_GetHistoryRelativePath());
}

string SYSTEM_BuildUniverseDir()
{
   return SYSTEM_JoinPath(SYSTEM_GetRootPath(), SYSTEM_GetUniverseRelativePath());
}

bool SYSTEM_DirectoryExists(const string path)
{
   if(StringLen(path) == 0)
      return false;

   int attributes = GetFileAttributesW(path);
   if(attributes == SYSTEM_INVALID_FILE_ATTRIBUTES)
      return false;

   return (attributes & SYSTEM_FILE_ATTRIBUTE_DIRECTORY) != 0;
}

bool SYSTEM_EnsureDirectory(const string path)
{
   if(StringLen(path) == 0)
      return false;

   if(SYSTEM_DirectoryExists(path))
      return true;

   int separator = -1;
   for(int index = StringLen(path) - 1; index >= 0; index--)
   {
      if(StringGetCharacter(path, index) == '\\')
      {
         separator = index;
         break;
      }
   }

   if(separator > 0)
   {
      string parent = StringSubstr(path, 0, separator);
      if(!SYSTEM_EnsureDirectory(parent))
         return false;
   }

   if(CreateDirectoryW(path, 0))
      return true;

   return GetLastError() == SYSTEM_ERROR_ALREADY_EXISTS;
}

bool SYSTEM_EnsureDirectories()
{
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildClientsDir()))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildLogsDir()))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildCacheDir()))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildHistoryDir()))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildUniverseDir()))
      return false;

   return true;
}

bool SYSTEM_EnsureAccountDirectories(const string account_id)
{
   if(StringLen(account_id) == 0)
      return false;

   if(!SYSTEM_EnsureDirectories())
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildAccountDir(account_id)))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildAccountJournalDir(account_id)))
      return false;
   if(!SYSTEM_EnsureDirectory(SYSTEM_BuildAccountStateDir(account_id)))
      return false;

   return true;
}

bool SYSTEM_InitPaths()
{
   string account_id = IntegerToString(AccountNumber());
   return SYSTEM_EnsureAccountDirectories(account_id);
}

#endif
