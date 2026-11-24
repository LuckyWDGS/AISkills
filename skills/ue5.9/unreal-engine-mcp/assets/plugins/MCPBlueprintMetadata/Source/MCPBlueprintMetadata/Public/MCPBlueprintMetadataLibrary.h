#pragma once

#include "Kismet/BlueprintFunctionLibrary.h"
#include "MCPBlueprintMetadataLibrary.generated.h"

class UBlueprint;

/**
 * Writes the Blueprint metadata the Details panel edits by hand: the Description of member
 * variables, local variables and functions (shown as hover tooltips) and function categories.
 * Editor Python: unreal.MCPBlueprintMetadataLibrary.set_function_tooltip(bp, "MyFunction", "...").
 * Every setter marks the Blueprint modified; compile and save as usual. An empty text clears the value.
 */
UCLASS()
class UMCPBlueprintMetadataLibrary : public UBlueprintFunctionLibrary
{
	GENERATED_BODY()

public:
	/** Description (tooltip) of a member variable declared by this Blueprint. False if the variable is not found. */
	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static bool SetMemberVariableTooltip(UBlueprint* Blueprint, FName VariableName, const FString& Tooltip);

	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static FString GetMemberVariableTooltip(UBlueprint* Blueprint, FName VariableName);

	/** Description (tooltip) of a local variable of a function graph. */
	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static bool SetLocalVariableTooltip(UBlueprint* Blueprint, FName FunctionName, FName VariableName, const FString& Tooltip);

	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static FString GetLocalVariableTooltip(UBlueprint* Blueprint, FName FunctionName, FName VariableName);

	/** Description (tooltip) of a function graph of this Blueprint. False if the function graph is not found. */
	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static bool SetFunctionTooltip(UBlueprint* Blueprint, FName FunctionName, const FString& Tooltip);

	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static FString GetFunctionTooltip(UBlueprint* Blueprint, FName FunctionName);

	/** Category of a function graph in My Blueprint, for example a Chinese group path. */
	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static bool SetFunctionCategory(UBlueprint* Blueprint, FName FunctionName, const FString& Category);

	UFUNCTION(BlueprintCallable, Category = "MCP|Blueprint Metadata")
	static FString GetFunctionCategory(UBlueprint* Blueprint, FName FunctionName);
};
