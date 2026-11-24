using UnrealBuildTool;

public class MCPBlueprintMetadata : ModuleRules
{
	public MCPBlueprintMetadata(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
		PublicDependencyModuleNames.AddRange(new string[] { "Core", "CoreUObject", "Engine" });
		PrivateDependencyModuleNames.AddRange(new string[] { "UnrealEd", "BlueprintGraph" });
	}
}
