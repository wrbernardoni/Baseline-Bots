import random
from reconchess import *


class AggressiveHorse(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.moveNum = 0

	def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
		self.board = board
		self.color = color

	def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):
		pass

	def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> \
			Optional[Square]:
		self.moveNum = self.moveNum + 1

		if (self.moveNum % 2) is 0:
			e_king_square = self.board.king(not self.color)
			if e_king_square:
				return e_king_square
		
		return random.choice(sense_actions)

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
			for attack in attackers:
				m = chess.Move(attack, e_king_square)
				if m in move_actions:
					return m

		class MvSrc:
			def __init__(self, board, iM, nm):
				self.brd = board
				self.initialMove = iM
				self.moveNum = nm

		moveSearch = [];
		im = MvSrc(self.board, None, 0);
		moveSearch.append(im)
		count = 0

		winningMove = [];

		while len(moveSearch) is not 0:
			count = count + 1
			if count > 1000:
				break

			im = moveSearch.pop(0);
			initialMove = im.initialMove;
			tempBoard = im.brd
			if tempBoard.turn is not self.color:
				tempBoard.push(chess.Move.null())

			e_king_square = tempBoard.king(not self.color)
			if e_king_square:
				attackers = tempBoard.attackers(self.color, e_king_square)
				if attackers:
					if initialMove in move_actions:
						winningMove.append(im)
			
			legalMoves = tempBoard.pseudo_legal_moves
			for move in legalMoves:
				if tempBoard.piece_at(move.from_square).piece_type is not chess.KNIGHT:
					continue

				mv = None
				if initialMove is None:
					mv = MvSrc(tempBoard.copy(), move, im.moveNum + 1)
				else:
					mv = MvSrc(tempBoard.copy(), initialMove, im.moveNum + 1)
				mv.brd.push(move)
				mv.brd.set_piece_at(move.from_square, chess.Piece(chess.PAWN, self.color))
				moveSearch.append(mv);

		while len(winningMove) > 0:
			winningMove.sort(key=lambda x : x.moveNum)
			mv = winningMove.pop(0).initialMove
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
