import random
from reconchess import *
from sortedcontainers import SortedList

class AggressiveTree(Player):
	def __init__(self):
		self.board = None
		self.color = None
		self.moveNum = 0
		self.lastMoves = []
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
		self.moveNum = self.moveNum + 1
		if self.my_piece_captured_square:
			return self.my_piece_captured_square
		
		for square, piece in self.board.piece_map().items():
			if piece.color == self.color:
				sense_actions.remove(square)
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

		m_king_square = self.board.king(self.color)
		if m_king_square:
			if self.board.turn is not self.color:
				self.board.push(chess.Move.null())
			attackers = self.board.attackers(not self.color, m_king_square)
			if attackers:
				legalMoves = self.board.legal_moves
				for move in legalMoves:
					tempBoard = self.board.copy()
					tempBoard.push(move)
					attackers = tempBoard.attackers(not self.color, m_king_square)
					if (attackers is None or len(attackers) is 0) and move in move_actions:
						return move

		class MvSrc:
			def __init__(self, board, iM, nm):
				self.brd = board
				self.initialMove = iM
				self.moveNum = nm

		moveSearch = SortedList(key=lambda x: x.moveNum);
		im = MvSrc(self.board, None, 0);
		moveSearch.add(im)
		count = 0
		winningMove = SortedList(key=lambda x: x.moveNum);

		while len(moveSearch) is not 0:
			count = count + 1
			if count > 5000:
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
						winningMove.add(im)
			
			legalMoves = tempBoard.legal_moves
			for move in legalMoves:
				if move.to_square in self.lastMoves:
					continue

				mv = None
				if initialMove is None:
					mv = MvSrc(tempBoard.copy(), move, im.moveNum + 1)
				else:
					mv = MvSrc(tempBoard.copy(), initialMove, im.moveNum + 1)
				mv.brd.push(move)
				numAttackers = len(mv.brd.attackers(not self.color, move.to_square))
				mv.moveNum = mv.moveNum + numAttackers
				moveSearch.add(mv);

		while len(winningMove) > 0:
			mv = winningMove.pop(0).initialMove
			self.lastMoves.append(mv.from_square)
			if len(self.lastMoves) > 5:
				self.lastMoves.pop(0)
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
