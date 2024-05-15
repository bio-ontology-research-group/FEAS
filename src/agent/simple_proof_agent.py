#!/usr/bin/env python3

import sys
import copy
root_dir = f"{__file__.split('src')[0]}"
if root_dir not in sys.path:
    sys.path.append(root_dir)
import logging
import typing
from src.rl.proof_action import ProofAction
from src.rl.abstraction import Agent, Policy
from src.rl.simple_proof_env import ProofEnv
from src.rl.simple_proof_env import ProgressState
from src.tools.dynamic_lean_proof_exec import DynamicProofExecutor as DynamicLeanProofExecutor


class ProofAgent(Agent):
    def __init__(self, 
        name: str, 
        policy: Policy, 
        should_checkpoint: bool = False, 
        proof_dump_file_name: str = None, 
        logger: logging.Logger = None):
        self._policy = policy
        self._name = name
        self._should_checkpoint = should_checkpoint
        self._proof_dump_file_name = proof_dump_file_name
        self.logger = logger or logging.getLogger(__name__)
        pass

    @property
    def name(self) -> str:
        return self._name

    def checkpoint(self):
        pass

    def clone(self):
        pass

    def run_episode(self, env: ProofEnv, max_steps_per_episode: int, render: bool):
        def _stop_policy(steps: int, info: typing.Dict[str, typing.Any]):
            return steps >= max_steps_per_episode
        def _policy_info_message(steps: int, info: typing.Dict[str, typing.Any]):
            return f"Step {steps}/{max_steps_per_episode}"
        self._run_episode_as_per_policy(env, _stop_policy, _policy_info_message, render)

    def run(self, env: ProofEnv, episodes: int, max_steps_per_episode: int, render: bool):
        assert isinstance(env, ProofEnv)
        while episodes > 0:
            self.run_episode(env, max_steps_per_episode, render)
            episodes -= 1
        pass

    def run_episodes_till_stop(self, env: ProofEnv, episodes: int, render: bool,
        stop_policy: typing.Callable[[int, typing.Dict[str, typing.Any]], bool], 
        policy_info_message: typing.Callable[[int, typing.Dict[str, typing.Any]], str]):
        assert isinstance(env, ProofEnv)
        while episodes > 0:
            self._run_episode_as_per_policy(env, stop_policy, policy_info_message, render)
            episodes -= 1
    def run_block_episodes_till_stop(self, env: ProofEnv, episodes: int, render: bool,
        stop_policy: typing.Callable[[int, typing.Dict[str, typing.Any]], bool],
        policy_info_message: typing.Callable[[int, typing.Dict[str, typing.Any]], str]):
        assert isinstance(env, ProofEnv)
        while episodes > 0:
            self._run_block_episode_as_per_policy(env, stop_policy, policy_info_message, render)
            episodes -= 1

    def _run_episode_as_per_policy(self,
            env: ProofEnv,
            stop_policy: typing.Callable[[int, typing.Dict[str, typing.Any]], bool],
            policy_info_message: typing.Callable[[int, typing.Dict[str, typing.Any]], str],
            render: bool):
        env.reset()
        done = False
        steps = 0
        total_reward = 0
        next_state = env.state
        additional_info = self._policy.get_efficiency_info()
        while not done and not stop_policy(steps, additional_info):
            self.logger.info(policy_info_message(steps, additional_info))
            self.logger.info("Asking policy for next action")
            action = self._policy(next_state)
            assert isinstance(action, ProofAction)
            self.logger.info(f"Got Action: {action}")
            if action.action_type != ProofAction.ActionType.EXIT:
                state, action, next_state, reward, done, info = env.step(action)
                # **IMPORTANT NOTE**: Here we update the action because sometimes the proof env can optimize the action
                # and return a different action which kind of aligns with the action taken by the
                # policy but only more efficient. This is slightly different traditional RL setting
                if render:
                    self.logger.info("**"*20)
                    env.render()
                    self.logger.info("**"*20)
                if action.action_type != ProofAction.ActionType.BACKTRACK:
                    # Don't update policy for backtracking actions, this will create a
                    # a very nasty loop in the policy.
                    self.logger.info("Updating policy")
                    self._policy.update(state, action, next_state, reward, done, info)
                    self.logger.info("Policy updated")
                steps += 1
                total_reward += reward
            else:
                self.logger.warning("Got EXIT action, exiting")
                break
            additional_info = self._policy.get_efficiency_info()
        env.dump_proof(self._proof_dump_file_name, additional_info)
        if self._should_checkpoint:
            self.logger.info("Checkpointing policy")
            self._policy.checkpoint()

    def _get_tactics(self, tactics):
        tactics_lists = []
        in_block = False
        block = ""
        block_delimiter = None
        brace_count = 0  # To track unmatched '{'

        for tactic in tactics:
            lines = tactic.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()

                if in_block:
                    block += '\n' + line
                    # Update brace count if we are in a "{" block
                    if block_delimiter == '}':
                        brace_count += line.count('{')
                        brace_count -= line.count('}')

                    # Check for end of block condition
                    if block_delimiter == '}' and brace_count == 0:
                        tactics_lists.append([block])
                        block = ""
                        in_block = False
                        brace_count = 0  # Reset brace count
                    elif block_delimiter == ',' and ',' in line and brace_count == 0:
                        tactics_lists.append([block])
                        block = ""
                        in_block = False
                    elif block_delimiter == '--' and not line.startswith('--'):
                        tactics_lists.append([block])
                        block = ""
                        in_block = False
                else:
                    if '{' in line:
                        brace_count = line.count('{') - line.count('}')
                        block_delimiter = '}'
                        block = line
                        in_block = True
                        # Immediately close the block if braces match on the same line
                        if brace_count == 0:
                            tactics_lists.append([block])
                            block = ""
                            in_block = False
                    elif 'calc' in line:
                        block_delimiter = ','
                        block = line
                        in_block = True
                        # Immediately close the block if a comma is found and no unmatched braces
                        if ',' in line and brace_count == 0:
                            tactics_lists.append([block])
                            block = ""
                            in_block = False
                    elif line.startswith('--'):
                        block_delimiter = '--'
                        block = line
                        in_block = True
                    else:
                        tactics_lists.append([line])

                i += 1

                # If we are still inside a block at the end of lines, we need to add it.
                if in_block and i == len(lines):
                    tactics_lists.append([block])
                    block = ""
                    in_block = False
                    brace_count = 0  # Reset brace count

        # Remove last entry if it only contains comment lines
        if tactics_lists and all(l.strip().startswith('--') for l in tactics_lists[-1][0].split('\n')):
            tactics_lists.pop()
        return tactics_lists

    def _run_multiple_tactics(self, env: ProofEnv, action: ProofAction, steps: int, total_reward: float):
        tactics = copy.deepcopy(action.kwargs["tactics"])
        qed = False
        tactics_lists = self._get_tactics(tactics)
        for i in range(len(tactics_lists)):
            new_action = ProofAction(ProofAction.ActionType.RUN_TACTIC, ProofAction.Language.LEAN, tactics=tactics_lists[i])
            if action.original_message is not None:
                new_action.original_message = copy.deepcopy(action.original_message)
                new_action.original_message['content'] = "[RUN TACTIC]\n" + tactics_lists[i][0] + "\n[END]"
            self.logger.info(f"Got Sub-Action: {new_action}")
            # self.logger.info(f"Got Sub-Action message of type {type(action.original_message)}: {action.original_message}")
            state, new_action, next_state, reward, done, info = env.step(new_action)

            self.logger.info("Updating policy")
            self._policy.update(state, new_action, next_state, reward, done, info)
            self.logger.info("Policy updated")
            steps += 1
            total_reward += reward
            additional_info = self._policy.get_efficiency_info()
            qed = next_state.training_data_format is not None and next_state.training_data_format.goal_description == DynamicLeanProofExecutor.ProofFinishedDescription
            if info.progress == ProgressState.FAILED or qed:
                break
        return next_state, qed, done, steps, total_reward, additional_info

    def _run_nlinarith(self, env: ProofEnv, original_message, steps: int, total_reward: float, additional_info):
        tactic = ["nlinarith,"]
        new_action = ProofAction(ProofAction.ActionType.RUN_TACTIC, ProofAction.Language.LEAN, tactics=tactic)
        new_action.original_message = copy.deepcopy(original_message)
        new_action.original_message['content'] = "[RUN TACTIC]\n" + tactic[0] + "\n[END]"
        self.logger.info(f"Got nlinarith Sub-Action: {new_action}")
        state, new_action, next_state, reward, done, info = env.step(new_action)
        if info.progress != ProgressState.FAILED:
            self.logger.info("Updating policy")
            self._policy.update(state, new_action, next_state, reward, done, info)
            self.logger.info("Policy updated")
            steps += 1
            total_reward += reward
            additional_info = self._policy.get_efficiency_info()
        return next_state, done, steps, total_reward, additional_info

    def _run_block_episode_as_per_policy(self,
            env: ProofEnv,
            stop_policy: typing.Callable[[int, typing.Dict[str, typing.Any]], bool],
            policy_info_message: typing.Callable[[int, typing.Dict[str, typing.Any]], str],
            render: bool):
        env.reset()
        done = False
        steps = 0
        total_reward = 0
        next_state = env.state
        additional_info = self._policy.get_efficiency_info()
        while not done and not stop_policy(steps, additional_info):
            self.logger.info(policy_info_message(steps, additional_info))
            self.logger.info("Asking policy for next action")
            action = self._policy(next_state)
            assert isinstance(action, ProofAction)
            self.logger.info(f"Got Action: {action}")
            if action.action_type == ProofAction.ActionType.RUN_TACTIC:
                next_state, qed, done, steps, total_reward, additional_info = self._run_multiple_tactics(env, action, steps, total_reward)
                if not qed and not done:
                    next_state, done, steps, total_reward, additional_info = self._run_nlinarith(env, action.original_message, steps, total_reward, additional_info)
            else:
                if action.action_type != ProofAction.ActionType.EXIT:
                    state, action, next_state, reward, done, info = env.step(action)
                    # **IMPORTANT NOTE**: Here we update the action because sometimes the proof env can optimize the action
                    # and return a different action which kind of aligns with the action taken by the
                    # policy but only more efficient. This is slightly different traditional RL setting
                    if render:
                        self.logger.info("**"*20)
                        env.render()
                        self.logger.info("**"*20)
                    if action.action_type != ProofAction.ActionType.BACKTRACK:
                        # Don't update policy for backtracking actions, this will create a
                        # a very nasty loop in the policy.
                        self.logger.info("Updating policy")
                        self._policy.update(state, action, next_state, reward, done, info)
                        self.logger.info("Policy updated")
                    steps += 1
                    total_reward += reward
                else:
                    self.logger.warning("Got EXIT action, exiting")
                    break
                additional_info = self._policy.get_efficiency_info()
        env.dump_proof(self._proof_dump_file_name, additional_info)
        if self._should_checkpoint:
            self.logger.info("Checkpointing policy")
            self._policy.checkpoint()