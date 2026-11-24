#include "MCPBlueprintMetadataLibrary.h"

#include "EdGraph/EdGraph.h"
#include "EdGraphSchema_K2.h"
#include "Engine/Blueprint.h"
#include "K2Node_FunctionEntry.h"
#include "Kismet2/BlueprintEditorUtils.h"
#include "Modules/ModuleManager.h"
#include "ScopedTransaction.h"

#define LOCTEXT_NAMESPACE "MCPBlueprintMetadata"

IMPLEMENT_MODULE(FDefaultModuleImpl, MCPBlueprintMetadata)

namespace
{
	UK2Node_FunctionEntry* FindFunctionEntry(UBlueprint* Blueprint, FName FunctionName)
	{
		if (!Blueprint)
		{
			return nullptr;
		}
		for (UEdGraph* Graph : Blueprint->FunctionGraphs)
		{
			if (Graph && Graph->GetFName() == FunctionName)
			{
				TArray<UK2Node_FunctionEntry*> Entries;
				Graph->GetNodesOfClass(Entries);
				return Entries.Num() == 1 ? Entries[0] : nullptr;
			}
		}
		return nullptr;
	}

	FBPVariableDescription* FindLocalVariable(UK2Node_FunctionEntry* Entry, FName VariableName)
	{
		return Entry ? Entry->LocalVariables.FindByPredicate([VariableName](const FBPVariableDescription& Var) { return Var.VarName == VariableName; }) : nullptr;
	}
}

bool UMCPBlueprintMetadataLibrary::SetMemberVariableTooltip(UBlueprint* Blueprint, FName VariableName, const FString& Tooltip)
{
	if (!Blueprint || FBlueprintEditorUtils::FindNewVariableIndex(Blueprint, VariableName) == INDEX_NONE)
	{
		return false;
	}
	const FScopedTransaction Transaction(LOCTEXT("SetVariableTooltip", "Set Variable Description"));
	Blueprint->Modify();
	if (Tooltip.IsEmpty())
	{
		FBlueprintEditorUtils::RemoveBlueprintVariableMetaData(Blueprint, VariableName, nullptr, FBlueprintMetadata::MD_Tooltip);
	}
	else
	{
		FBlueprintEditorUtils::SetBlueprintVariableMetaData(Blueprint, VariableName, nullptr, FBlueprintMetadata::MD_Tooltip, Tooltip);
	}
	return true;
}

FString UMCPBlueprintMetadataLibrary::GetMemberVariableTooltip(UBlueprint* Blueprint, FName VariableName)
{
	FString Value;
	if (Blueprint)
	{
		FBlueprintEditorUtils::GetBlueprintVariableMetaData(Blueprint, VariableName, nullptr, FBlueprintMetadata::MD_Tooltip, Value);
	}
	return Value;
}

bool UMCPBlueprintMetadataLibrary::SetLocalVariableTooltip(UBlueprint* Blueprint, FName FunctionName, FName VariableName, const FString& Tooltip)
{
	UK2Node_FunctionEntry* Entry = FindFunctionEntry(Blueprint, FunctionName);
	if (!FindLocalVariable(Entry, VariableName))
	{
		return false;
	}
	const FScopedTransaction Transaction(LOCTEXT("SetLocalVariableTooltip", "Set Local Variable Description"));
	Entry->Modify();
	FBPVariableDescription* Variable = FindLocalVariable(Entry, VariableName);
	if (Tooltip.IsEmpty())
	{
		Variable->RemoveMetaData(FBlueprintMetadata::MD_Tooltip);
	}
	else
	{
		Variable->SetMetaData(FBlueprintMetadata::MD_Tooltip, Tooltip);
	}
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

FString UMCPBlueprintMetadataLibrary::GetLocalVariableTooltip(UBlueprint* Blueprint, FName FunctionName, FName VariableName)
{
	const FBPVariableDescription* Variable = FindLocalVariable(FindFunctionEntry(Blueprint, FunctionName), VariableName);
	return Variable && Variable->HasMetaData(FBlueprintMetadata::MD_Tooltip) ? Variable->GetMetaData(FBlueprintMetadata::MD_Tooltip) : FString();
}

bool UMCPBlueprintMetadataLibrary::SetFunctionTooltip(UBlueprint* Blueprint, FName FunctionName, const FString& Tooltip)
{
	UK2Node_FunctionEntry* Entry = FindFunctionEntry(Blueprint, FunctionName);
	if (!Entry)
	{
		return false;
	}
	const FScopedTransaction Transaction(LOCTEXT("SetFunctionTooltip", "Set Function Description"));
	Entry->Modify();
	Entry->MetaData.ToolTip = FText::FromString(Tooltip);
	FBlueprintEditorUtils::MarkBlueprintAsModified(Blueprint);
	return true;
}

FString UMCPBlueprintMetadataLibrary::GetFunctionTooltip(UBlueprint* Blueprint, FName FunctionName)
{
	const UK2Node_FunctionEntry* Entry = FindFunctionEntry(Blueprint, FunctionName);
	return Entry ? Entry->MetaData.ToolTip.ToString() : FString();
}

bool UMCPBlueprintMetadataLibrary::SetFunctionCategory(UBlueprint* Blueprint, FName FunctionName, const FString& Category)
{
	UK2Node_FunctionEntry* Entry = FindFunctionEntry(Blueprint, FunctionName);
	if (!Entry)
	{
		return false;
	}
	const FScopedTransaction Transaction(LOCTEXT("SetFunctionCategory", "Set Function Category"));
	FBlueprintEditorUtils::SetBlueprintFunctionOrMacroCategory(Entry->GetGraph(), FText::FromString(Category));
	return true;
}

FString UMCPBlueprintMetadataLibrary::GetFunctionCategory(UBlueprint* Blueprint, FName FunctionName)
{
	const UK2Node_FunctionEntry* Entry = FindFunctionEntry(Blueprint, FunctionName);
	return Entry ? Entry->MetaData.Category.ToString() : FString();
}

#undef LOCTEXT_NAMESPACE
