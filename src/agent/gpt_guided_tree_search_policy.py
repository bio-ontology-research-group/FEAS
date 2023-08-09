#!/usr/bin/env python3

import sys
root_dir = f"{__file__.split('src')[0]}"
if root_dir not in sys.path:
    sys.path.append(root_dir)
import uuid
import typing
import os
import math
from enum import Enum
from dataclasses import dataclass
from dataclasses_json import dataclass_json
from abc import ABC, abstractmethod
from src.rl.q_tree import QGraph, QInfo, QTreeNode
from src.rl.abstraction import Policy
from src.rl.simple_proof_env import ProofAction, ProofState, ProofEnvInfo

class TreeSearchActionType(Enum):
    # The action to generate a summary prompt
    NEXT_ACTION_SUMMARY_PROMPT = 'NEXT_ACTION_SUMMARY_PROMPT'
    # The action to generate a failed action summary prompt
    FAILED_ACTION_SUMMARY_PROMPT = 'FAILED_ACTION_SUMMARY_PROMPT'
    # State is harder than previous state(s)
    HARDER_STATE_SUMMARY_PROMPT = 'HARDER_STATE_SUMMARY_PROMPT'
    # The action to generate a cyclic state summary prompt
    CYCLIC_STATE_SUMMARY_PROMPT = 'CYCLIC_STATE_SUMMARY_PROMPT'
    # The action to backtrack to the previous state
    BACKTRACK = 'BACKTRACK'
    # The action to stop the search
    STOP = 'STOP'

@dataclass_json
@dataclass
class PromptSummary:
    actions_to_avoid: typing.List[ProofAction]
    state: ProofState
    pass

class TreeSearchAction:
    def __init__(self, 
        action_type: TreeSearchActionType, 
        **kwargs):
        self.action_type = action_type
        self.kwargs = kwargs

class StateType(Enum):
    # The state is Undiscovered
    UNDISCOVERED = 'UNDISCOVERED'
    # The state is Discovered
    DISCOVERED = 'DISCOVERED'
    # The state is Backtracked
    BACKTRACKED = 'BACKTRACKED'

@dataclass_json
@dataclass
class ProofQInfo(QInfo):
    proof_env_info: ProofEnvInfo
    state_type: StateType
    def serialize(self) -> str:
        return self.to_json()
    
    @staticmethod
    def deserialize(data: str) -> 'ProofQInfo':
        return ProofQInfo.schema().loads(data)

@dataclass_json
@dataclass
class ProofQTreeNode(QTreeNode):
    prev_state: ProofState
    actions: typing.List[ProofAction]
    next_state: typing.List[ProofState]
    qinfo: typing.List[ProofQInfo]

    def serialize(self) -> str:
        return self.to_json()
    
    @staticmethod
    def deserialize(data: str) -> 'ProofQTreeNode':
        return ProofQTreeNode.schema().loads(data)


class ProofQTree(QGraph):
    def serialize(self) -> str:
        # Conver to ProofQTreeNodes
        qtree_nodes = []
        for prev_state, edges in self.edges.items():
            actions = []
            next_states = []
            qinfos = []
            for action, state_info in edges.items():
                qinfo = state_info.qinfo
                next_state = state_info.next_state
                actions.append(action)
                next_states.append(next_state)
                qinfos.append(qinfo)
            qtree_nodes.append(ProofQTreeNode(prev_state, actions, next_states, qinfos))
        return ProofQTreeNode.schema().dumps(qtree_nodes, many=True)
    
    @staticmethod
    def deserialize(data: str) -> 'ProofQTree':
        qtree_nodes : typing.List[ProofQTreeNode] = ProofQTreeNode.schema().loads(data, many=True)
        qtree = ProofQTree()
        for qtree_node in qtree_nodes:
            for action, next_state, qinfo in zip(qtree_node.actions, qtree_node.next_state, qtree_node.qinfo):
                qtree.add(qtree_node.prev_state, action, next_state, qinfo)
        return qtree

class TreeSearchAlgorithm(ABC):
    @abstractmethod
    def __call__(self, tree: ProofQTree, state: ProofState) -> TreeSearchAction:
        pass

    @abstractmethod
    def update_new_node(self, tree: ProofQTree, state: ProofState, action: ProofAction, next_state: ProofState, reward: float, done: bool, info: ProofEnvInfo):
        pass

    @abstractmethod
    def estimate_q_value(self, tree: ProofQTree, state: ProofState, action: ProofAction, next_state: ProofState, reward: float, done: bool, info: ProofEnvInfo) -> float:
        pass

class GptPolicyPrompter(ABC):
    @abstractmethod
    def __call__(self, tree_search_action: TreeSearchAction) -> ProofAction:
        pass

class GptGuidedTreeSearchPolicy(Policy):
    def __init__(self, 
        checkpoint_dir: str, 
        checkpoint_filename: str,
        policy_prompter: GptPolicyPrompter,
        tree_search_algorithm: TreeSearchAlgorithm, 
        checkpoint_on_exit: bool = True):
        assert tree_search_algorithm is not None, "Tree search algorithm cannot be None"
        assert policy_prompter is not None, "Policy prompter cannot be None"
        os.path.exists(checkpoint_dir), f"Checkpoint file {checkpoint_dir} does not exist"
        checkpoint_filename is not None, "Checkpoint filename cannot be None"
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_filename = checkpoint_filename
        self._proof_q_tree : ProofQTree = None
        self.checkpoint_on_exit = checkpoint_on_exit
        self.policy_prompter = None
        self._tree_search_algorithm = tree_search_algorithm
        self._policy_prompter = policy_prompter
        self._loaded = False
    
    def __enter__(self):
        if not self.load_from_checkpoint_if_exists():
            self._proof_q_tree = ProofQTree()
        self._loaded = True
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        assert self._loaded, "Policy was not loaded"
        if self.checkpoint_on_exit:
            self.checkpoint()
    
    def load_from_checkpoint_if_exists(self):
        checkpoint_path = os.path.join(self.checkpoint_dir, self.checkpoint_filename)
        if os.path.exists(checkpoint_path) and self._proof_q_tree is None:
            with open(checkpoint_path, 'r') as f:
                self._proof_q_tree = ProofQTree.deserialize(f.read())
            return True
        return False
    
    def checkpoint(self):
        checkpoint_path = os.path.join(self.checkpoint_dir, self.checkpoint_filename)
        self._checkpoint_in_file(checkpoint_path)

    def __call__(self, state: ProofState) -> ProofAction:
        tree_search_action : TreeSearchAction = self._tree_search_algorithm(self._proof_q_tree, state)
        if tree_search_action.action_type == TreeSearchActionType.NEXT_ACTION_SUMMARY_PROMPT \
        or tree_search_action.action_type == TreeSearchActionType.FAILED_ACTION_SUMMARY_PROMPT \
        or tree_search_action.action_type == TreeSearchActionType.CYCLIC_STATE_SUMMARY_PROMPT:
            action = self._policy_prompter(tree_search_action)
        elif tree_search_action.action_type == TreeSearchActionType.BACKTRACK:
            action = ProofAction(ProofAction.ActionType.BACKTRACK)
        elif tree_search_action.action_type == TreeSearchActionType.STOP:
            action = ProofAction(ProofAction.ActionType.EXIT)
        else:
            raise Exception(f"Unknown tree search action {tree_search_action}")
        return action

    def update(self, state: ProofState, action: ProofAction, next_state: ProofState, reward: float, done: bool, info: ProofEnvInfo):
        qval = -math.inf
        proof_q_info = ProofQInfo(reward, done, qval, info)
        self._proof_q_tree.add(state, action, next_state, proof_q_info)
        self._tree_search_algorithm.update_new_node(self._proof_q_tree, state, action, next_state, reward, done, info)
        qval = self._tree_search_algorithm.estimate_q_value(self._proof_q_tree, state, action, next_state, reward, done, info)
        self._proof_q_tree.update_qinfo(state, action, next_state, proof_q_info)

    def clone(self) -> 'GptGuidedTreeSearchPolicy':
        guid = str(uuid.uuid4())
        checkpoint_filename_without_ext, ext = os.path.splitext(self.checkpoint_filename)
        checkpoint_filename = f"{checkpoint_filename_without_ext}-{guid}.{ext}"
        self._checkpoint_in_file(os.path.join(self.checkpoint_dir, checkpoint_filename))
        copy_obj = GptGuidedTreeSearchPolicy(self.checkpoint_dir, checkpoint_filename)
        return copy_obj

    def _checkpoint_in_file(self, checkpoint_path: str):
        os.path.exists(checkpoint_path), f"Checkpoint file {checkpoint_path} does not exist"
        with open(checkpoint_path, 'w') as f:
            f.write(self._proof_q_tree.serialize())