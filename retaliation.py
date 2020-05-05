import random
from reconchess import *

class RandomRetaliation(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.my_piece_captured_square = None

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		self.my_piece_captured_square = capture_square
		if captured_my_piece:
			self.board.remove_piece_at(capture_square)

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		#e_king_square = self.board.king(not self.color)
		#if e_king_square:
		#	return e_king_square
		
		return None

	def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
		for square, piece in sense_result:
			if piece is None:
				self.board.remove_piece_at(square)
			else:
				self.board.set_piece_at(square, piece)

	def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
		e_king_square = self.board.king(not self.color)
		if e_king_square:
			attackers = self.board.attackers(self.color, e_king_square)
			if attackers:
				attack = attackers.pop();
				mv = chess.Move(attack, e_king_square)
				if mv in move_actions:
					return mv

		if self.my_piece_captured_square:
			attackers = self.board.attackers(self.color, self.my_piece_captured_square)
			if attackers:
				attack = attackers.pop();
				mv = chess.Move(attack, self.my_piece_captured_square)
				if mv in move_actions:
					return mv

		return random.choice(move_actions + [None])

	def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
						   captured_opponent_piece: bool, capture_square: Optional[Square]):
		if taken_move is not None:
			self.board.push(taken_move)

	def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
						game_history: GameHistory):
		pass
