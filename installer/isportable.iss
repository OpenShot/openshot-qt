// -- IsPortable.iss --
// Include file with support functions for portable mode
//
[Code]
function PortableCheck: Boolean;
begin
  Result := ExpandConstant('{param:portable|0}') = '1';
end;

function PreservePortableData: Boolean;
begin
  // Also protect an existing portable copy if /portable=1 was omitted.
  Result := PortableCheck or FileExists(ExpandConstant('{app}\portable'));
end;

procedure CleanPortableProgramFiles;
var
  FindRec: TFindRec;
  Path: String;
begin
  // Remove old binaries, but never recursively delete the portable user data.
  if FindFirst(ExpandConstant('{app}\*'), FindRec) then
  begin
    try
      repeat
        if (FindRec.Name <> '.') and (FindRec.Name <> '..') and
           (CompareText(FindRec.Name, '.openshot_qt') <> 0) and
           (CompareText(FindRec.Name, 'portable') <> 0) then
        begin
          Path := AddBackslash(ExpandConstant('{app}')) + FindRec.Name;
          if not DelTree(Path,
              (FindRec.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0, True, True) then
            RaiseException('Unable to remove old OpenShot files: ' + Path);
        end;
      until not FindNext(FindRec);
    finally
      FindClose(FindRec);
    end;
  end;
end;

<event('CurStepChanged')>
procedure IsPortableCurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) and PreservePortableData then
    CleanPortableProgramFiles;
  if (CurStep = ssPostInstall) and PortableCheck then
  begin
    if not SaveStringToFile(ExpandConstant('{app}\portable'), '', False) then
      RaiseException('Unable to create the OpenShot portable marker.');
  end;
end;

function GetAppId(Param: String): String;
begin
  Result := Param;
  if PortableCheck then
    Result := Result + ' Portable';
end;

function GetDefaultDirName(Param: String): String;
begin
  if PortableCheck then
    Result := '{autodesktop}'
  else
    Result := '{autopf}';
  Result := ExpandConstant(AddBackslash(Result) + Param);
end;

<event('InitializeWizard')>
procedure IsPortableInitializeWizard;
begin
  if PortableCheck then
    WizardForm.NoIconsCheck.Checked := True;
end;

<event('ShouldSkipPage')>
function IsPortableShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = wpSelectProgramGroup) and PortableCheck;
end;
